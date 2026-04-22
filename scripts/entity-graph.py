#!/usr/bin/env python3
"""Entity Graph — extract entities from daily summaries and maintain Obsidian entity pages.

Usage:
    entity-graph.py                 # Process unprocessed summaries + notes
    entity-graph.py --backfill N    # Process last N days regardless of state
    entity-graph.py --seed          # Seed alias map from known entities
    entity-graph.py --dry-run       # Show what would be processed without writing
    entity-graph.py --notes-only    # Process only personal handwritten notes

Reads daily summary files (memory/YYYY-MM-DD-summary.md) and processed handwritten
notes (Personal Notes/Personal-Notes-*.md), extracts entities and relationships via
Claude CLI, and creates/updates entity pages in the Obsidian vault at
Entities/{type}/{name}.md.

Entity pages use the Compiled Truth + Timeline format:
- Compiled Truth: curated current-state summary (regenerated on updates)
- Timeline: dated entries from each day's conversations
- Relationships: markdown links to other entities (Obsidian-compatible)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from bot.config import load_raw_config  # noqa: E402

TZ = ZoneInfo("America/Chicago")
DEFAULT_MODEL = "sonnet"  # Sonnet is plenty for structured extraction

VAULT_PATH = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
ENTITIES_DIR = VAULT_PATH / "Entities"
# Memory and data live in deployed dir, not source
DEPLOYED_DIR = Path.home() / "clawcode"
MEMORY_DIR = DEPLOYED_DIR / "memory"
DATA_DIR = DEPLOYED_DIR / "data"
STATE_PATH = DATA_DIR / "entity-graph-state.json"
ALIASES_PATH = DATA_DIR / "entity-aliases.json"

PERSONAL_NOTES_DIR = VAULT_PATH / "Personal Notes"

ENTITY_TYPES = ["People", "Projects", "Courses", "Organizations", "Tools"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("entity-graph")


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"processed_dates": {}, "last_run": None}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now(TZ).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def load_aliases() -> dict:
    if ALIASES_PATH.exists():
        try:
            return json.loads(ALIASES_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"entities": {}, "alias_to_canonical": {}}


def save_aliases(aliases: dict) -> None:
    ALIASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALIASES_PATH.write_text(json.dumps(aliases, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Summary discovery
# ---------------------------------------------------------------------------


def find_summaries(backfill_days: int | None = None) -> list[tuple[str, Path]]:
    """Find summary files to process. Returns [(date_str, path), ...]."""
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})-summary\.md$")
    summaries = []

    for f in sorted(MEMORY_DIR.glob("*-summary.md")):
        m = pattern.search(f.name)
        if m:
            summaries.append((m.group(1), f))

    if backfill_days is not None:
        cutoff = (datetime.now(TZ) - timedelta(days=backfill_days)).strftime("%Y-%m-%d")
        summaries = [(d, p) for d, p in summaries if d >= cutoff]

    return summaries


def find_unprocessed(state: dict) -> list[tuple[str, Path]]:
    """Find summaries not yet processed."""
    processed = state.get("processed_dates", {})
    all_summaries = find_summaries()
    return [(d, p) for d, p in all_summaries if d not in processed]


# ---------------------------------------------------------------------------
# Personal notes discovery
# ---------------------------------------------------------------------------


def parse_personal_notes() -> list[tuple[str, str]]:
    """Parse Personal-Notes-*.md files into (date_str, section_text) tuples.

    Notes use ## YYYYMMDD headers. Returns dates in YYYY-MM-DD format for
    consistency with summaries.
    """
    header_re = re.compile(r"^## (\d{4})(\d{2})(\d{2})\b", re.MULTILINE)
    entries = []

    for notes_file in sorted(PERSONAL_NOTES_DIR.glob("Personal-Notes-*.md")):
        text = notes_file.read_text()
        splits = list(header_re.finditer(text))
        if not splits:
            continue

        for i, match in enumerate(splits):
            year, month, day = match.group(1), match.group(2), match.group(3)
            date_str = f"{year}-{month}-{day}"
            start = match.start()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            section = text[start:end].strip()
            if section:
                entries.append((date_str, section))

    return sorted(entries, key=lambda x: x[0])


def find_unprocessed_notes(state: dict) -> list[tuple[str, str]]:
    """Find personal note sections needing processing.

    Re-processes anything dated >= (latest processed note date - 1 day) to
    catch partial notes that were scanned in later batches. Notes older than
    that cutoff are skipped if already processed.
    """
    processed = state.get("processed_notes_dates", {})
    all_notes = parse_personal_notes()

    if processed:
        latest = max(processed.keys())
        # Subtract one day from the latest processed date to catch partial batches
        latest_dt = datetime.strptime(latest, "%Y-%m-%d")
        cutoff = (latest_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        return [(d, text) for d, text in all_notes if d >= cutoff]
    else:
        return all_notes


# ---------------------------------------------------------------------------
# Claude CLI interaction
# ---------------------------------------------------------------------------



def get_claude_path(config: dict) -> str:
    return str(Path(config["claude"]["path"]).expanduser())


def call_claude_json(prompt: str, config: dict) -> dict | list | None:
    """Call Claude CLI with a prompt, expect JSON output."""
    claude_path = get_claude_path(config)
    if not Path(claude_path).exists():
        raise FileNotFoundError(f"Claude CLI not found at {claude_path}")

    cmd = [
        claude_path,
        "--print",
        "--model", DEFAULT_MODEL,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        env=env,
        timeout=300,
    )

    if result.returncode != 0:
        logger.error("Claude CLI failed (rc=%d): %s", result.returncode, result.stderr)
        return None

    # Parse the response — Claude CLI wraps in {"result": "..."} or {"content": [...]}
    try:
        data = json.loads(result.stdout)
        text = ""
        if isinstance(data, dict) and "result" in data:
            text = data["result"]
        elif isinstance(data, dict) and "content" in data:
            parts = []
            for block in data["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            text = "\n".join(parts)
        else:
            text = result.stdout.strip()

        # Extract JSON from the text (may be wrapped in markdown code fences)
        json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try parsing the whole text as JSON
        return json.loads(text)

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse Claude response as JSON: %s", e)
        logger.debug("Raw response: %s", result.stdout[:500])
        return None


def call_claude_text(prompt: str, config: dict) -> str | None:
    """Call Claude CLI with a prompt, return plain text."""
    claude_path = get_claude_path(config)
    if not Path(claude_path).exists():
        raise FileNotFoundError(f"Claude CLI not found at {claude_path}")

    cmd = [
        claude_path,
        "--print",
        "--model", DEFAULT_MODEL,
        "--dangerously-skip-permissions",
    ]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        env=env,
        timeout=300,
    )

    if result.returncode != 0:
        logger.error("Claude CLI failed (rc=%d): %s", result.returncode, result.stderr)
        return None

    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are an entity extraction system. Read the following daily conversation summary and extract all mentioned entities and their relationships.

ENTITY TYPES:
- person: Named individuals (not "the user" or "Scott" — Scott is the author, skip him)
- project: Software projects, initiatives, products being built
- course: Academic courses, classes
- organization: Companies, universities, groups, teams
- tool: Software tools, frameworks, libraries, services

KNOWN ENTITIES (match these when possible, don't create duplicates):
{known_entities}

OUTPUT FORMAT — respond with ONLY this JSON, no other text:
{{
  "entities": [
    {{
      "name": "Canonical Name",
      "type": "person|project|course|organization|tool",
      "aliases": ["Other Name", "Abbreviation"],
      "facts": ["One sentence fact learned today", "Another fact"],
      "relationships": [
        {{"target": "Other Entity Name", "target_type": "type", "relation": "short description"}}
      ]
    }}
  ]
}}

RULES:
- Skip Scott Person — he's the author, not an entity to track
- Skip generic mentions ("the professor" without a name)
- Match existing entities by name/alias before creating new ones
- If a name matches a KNOWN ENTITY canonical or alias (even with different
  capitalization or spelling — "Marshall" vs "Marshal", "clawcode" vs
  "ClawCode"), USE THE CANONICAL exactly as listed. Do not invent a new
  entity for a near-match spelling.
- Keep facts specific to what was learned THIS day. Do not restate facts
  that are likely already captured — aim for NEW information only.
- Relationships should be between two named entities
- If no entities are found, return {{"entities": []}}

SUMMARY FOR {date}:
{summary}"""


def extract_entities(date_str: str, summary_text: str, aliases: dict, config: dict) -> list[dict] | None:
    """Extract entities from a summary using Claude."""
    # Build known entities string for the prompt
    known = []
    for canonical, info in aliases.get("entities", {}).items():
        aka = ", ".join(info.get("aliases", []))
        aka_str = f" (aka: {aka})" if aka else ""
        known.append(f"- [{info.get('type', '?')}] {canonical}{aka_str}")
    known_str = "\n".join(known) if known else "(none yet)"

    prompt = EXTRACTION_PROMPT.format(
        known_entities=known_str,
        date=date_str,
        summary=summary_text,
    )

    result = call_claude_json(prompt, config)
    if result and isinstance(result, dict) and "entities" in result:
        return result["entities"]
    return None


# ---------------------------------------------------------------------------
# Alias management
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Convert entity name to filename slug."""
    slug = re.sub(r"[^\w\s-]", "", name)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def type_dir(entity_type: str) -> str:
    """Map entity type to directory name."""
    mapping = {
        "person": "People",
        "project": "Projects",
        "course": "Courses",
        "organization": "Organizations",
        "tool": "Tools",
    }
    return mapping.get(entity_type, "Other")


def resolve_entity(name: str, entity_type: str, entity_aliases: list[str], aliases: dict) -> str:
    """Resolve an entity name to its canonical form, updating aliases if new."""
    alias_map = aliases.setdefault("alias_to_canonical", {})
    entities = aliases.setdefault("entities", {})

    # Check exact match on canonical names
    key = f"{entity_type}:{name}"
    if key in entities:
        return name

    # Check alias map (case-insensitive)
    for alias_key, canonical_key in alias_map.items():
        if alias_key.lower() == name.lower():
            return canonical_key.split(":", 1)[1] if ":" in canonical_key else canonical_key

    # Check if any provided alias matches
    for alias in entity_aliases:
        for alias_key, canonical_key in alias_map.items():
            if alias_key.lower() == alias.lower():
                # Add new alias for existing entity
                alias_map[name.lower()] = canonical_key
                return canonical_key.split(":", 1)[1] if ":" in canonical_key else canonical_key

    # New entity — register it
    entities[key] = {
        "type": entity_type,
        "aliases": entity_aliases,
        "filename": f"{slugify(name)}.md",
        "first_seen": datetime.now(TZ).strftime("%Y-%m-%d"),
    }
    alias_map[name.lower()] = key
    for alias in entity_aliases:
        alias_map[alias.lower()] = key

    return name


# ---------------------------------------------------------------------------
# Entity page management
# ---------------------------------------------------------------------------


def entity_path(canonical_name: str, entity_type: str) -> Path:
    """Get the vault path for an entity page."""
    return ENTITIES_DIR / type_dir(entity_type) / f"{slugify(canonical_name)}.md"


def parse_entity_page(path: Path) -> dict:
    """Parse an existing entity page into sections."""
    if not path.exists():
        return {"frontmatter": {}, "compiled_truth": "", "relationships": [], "timeline": []}

    text = path.read_text()

    # Extract frontmatter
    frontmatter = {}
    body = text
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            pass
        body = fm_match.group(2)

    # Split on sections
    sections = {"compiled_truth": "", "relationships": [], "timeline": []}

    # Extract compiled truth (between ## Compiled Truth and next ##)
    ct_match = re.search(r"## Compiled Truth\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if ct_match:
        sections["compiled_truth"] = ct_match.group(1).strip()

    # Extract relationships
    rel_match = re.search(r"## Relationships\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if rel_match:
        sections["relationships"] = [
            line.strip() for line in rel_match.group(1).strip().split("\n")
            if line.strip().startswith("- ")
        ]

    # Extract timeline entries
    tl_match = re.search(r"## Timeline\n\n(.*?)$", body, re.DOTALL)
    if tl_match:
        sections["timeline"] = tl_match.group(1).strip()

    return {"frontmatter": frontmatter, **sections}


def build_relationship_line(target_name: str, target_type: str, relation: str) -> str:
    """Build an Obsidian-compatible relationship line."""
    target_dir = type_dir(target_type)
    target_slug = slugify(target_name)
    # Use relative path from current entity's type dir
    return f"- [{target_name}](../{target_dir}/{target_slug}.md) — {relation}"


def write_entity_page(
    canonical_name: str,
    entity_type: str,
    new_facts: list[str],
    new_relationships: list[str],
    date_str: str,
    aliases_list: list[str],
    existing: dict | None = None,
) -> Path:
    """Create or update an entity page."""
    path = entity_path(canonical_name, entity_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    if existing is None:
        existing = parse_entity_page(path)

    fm = existing["frontmatter"]
    fm["entity_type"] = entity_type
    fm["canonical_name"] = canonical_name
    if aliases_list:
        fm["aliases"] = list(set(fm.get("aliases", []) + aliases_list))
    fm["last_updated"] = date_str
    if "first_seen" not in fm:
        fm["first_seen"] = date_str

    # Merge relationships (deduplicate by target name)
    existing_rels = existing.get("relationships", [])
    existing_targets = set()
    for rel in existing_rels:
        # Extract target name from markdown link
        m = re.search(r"\[([^\]]+)\]", rel)
        if m:
            existing_targets.add(m.group(1).lower())

    for rel_line in new_relationships:
        m = re.search(r"\[([^\]]+)\]", rel_line)
        if m and m.group(1).lower() not in existing_targets:
            existing_rels.append(rel_line)
            existing_targets.add(m.group(1).lower())

    # Append to timeline
    timeline_existing = existing.get("timeline", "")
    timeline_entry = f"### {date_str}\n" + "\n".join(f"- {fact}" for fact in new_facts)

    if timeline_existing:
        # Check if this date already has an entry
        if f"### {date_str}" in timeline_existing:
            # Append facts to existing date entry
            timeline_parts = timeline_existing.split(f"### {date_str}")
            before = timeline_parts[0]
            after_parts = timeline_parts[1].split("\n### ", 1)
            existing_entry = after_parts[0]
            rest = "\n### " + after_parts[1] if len(after_parts) > 1 else ""
            new_bullets = "\n".join(f"- {fact}" for fact in new_facts)
            timeline = f"{before}### {date_str}{existing_entry}\n{new_bullets}{rest}"
        else:
            # Insert at top (most recent first)
            timeline = f"{timeline_entry}\n\n{timeline_existing}"
    else:
        timeline = timeline_entry

    # Compiled truth stays as-is for now — regenerated separately
    compiled_truth = existing.get("compiled_truth", "*Pending synthesis.*")

    # Build the page
    fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
    rels_str = "\n".join(existing_rels) if existing_rels else "*None yet.*"

    content = f"""---
{fm_yaml}
---

# {canonical_name}

## Compiled Truth

{compiled_truth}

## Relationships

{rels_str}

## Timeline

{timeline}
"""

    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# Compiled truth regeneration
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """You are synthesizing a "compiled truth" — a concise, current-state summary of an entity based on everything known from the timeline below.

Entity: {name} (type: {entity_type})

Timeline entries (most recent first):
{timeline}

Write 2-5 sentences capturing what is currently true about this entity. Focus on:
- Who/what they are (role, purpose, status)
- How they relate to Scott Person's life/work
- Any recent significant developments

Be factual and concise. No headers, no bullets — just prose. Do not start with the entity name."""


def regenerate_compiled_truth(
    canonical_name: str, entity_type: str, config: dict
) -> str | None:
    """Regenerate compiled truth from timeline entries."""
    path = entity_path(canonical_name, entity_type)
    if not path.exists():
        return None

    existing = parse_entity_page(path)
    timeline = existing.get("timeline", "")
    if not timeline or timeline == "*Pending synthesis.*":
        return None

    prompt = SYNTHESIS_PROMPT.format(
        name=canonical_name,
        entity_type=entity_type,
        timeline=timeline,
    )

    result = call_claude_text(prompt, config)
    if result:
        # Update the page with new compiled truth
        existing["compiled_truth"] = result
        fm = existing["frontmatter"]
        fm["last_updated"] = datetime.now(TZ).strftime("%Y-%m-%d")

        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
        rels = existing.get("relationships", [])
        rels_str = "\n".join(rels) if rels else "*None yet.*"
        timeline_str = existing.get("timeline", "")

        content = f"""---
{fm_yaml}
---

# {canonical_name}

## Compiled Truth

{result}

## Relationships

{rels_str}

## Timeline

{timeline_str}
"""
        path.write_text(content)
        return result

    return None


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed_aliases() -> dict:
    """Pre-populate aliases from memory/topics/ files."""
    aliases = load_aliases()

    # Known entities to seed
    seeds = [
        ("David Cochran", "person", ["Dr. Cochran", "Cochran", "David"]),
        ("Robert Norman", "person", ["Norman"]),
        ("Newman University", "organization", ["Newman"]),
        ("Tiber Solutions", "organization", ["Tiber"]),
        ("Data Preprocessing", "course", ["DSCI-6423", "Data Preprocessing"]),
        ("Data Engineering", "course", ["DSCI-6313"]),
        ("Data Analysis and Visualization", "course", ["Data Analysis", "DAV"]),
        ("Data Analytics Seminar", "course", ["Analytics Seminar"]),
        ("ClawCode", "project", ["Clawcode", "clawcode"]),
        ("Life Agent", "project", ["life-agent", "Life-Agent"]),
        ("GBrain", "project", ["gbrain"]),
        ("Marshal", "project", ["Marshall"]),
        ("Claude Code", "tool", ["claude-code", "Claude CLI"]),
        ("Hermes Agent", "tool", ["Hermes", "hermes"]),
        ("QMD", "tool", ["qmd"]),
        ("Apple Shortcuts", "tool", ["Apple Shortcuts MCP", "Apple Shortcuts MCP server", "Shortcuts"]),
        ("Jennifer Person", "person", ["Jen", "Jennifer"]),
        ("Ellie Person", "person", ["Ellie", "Elizabeth"]),
        ("Jason Person", "person", ["Jason"]),
        ("Kent Haury", "person", ["Kent"]),
        ("Garry Tan", "person", ["Tan"]),
        ("Tate Cuffy", "person", ["Tate"]),
    ]

    for name, etype, alias_list in seeds:
        resolve_entity(name, etype, alias_list, aliases)

    save_aliases(aliases)
    logger.info("Seeded %d entities", len(seeds))
    return aliases


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


def process_summary(
    date_str: str, summary_path: Path, aliases: dict, config: dict, dry_run: bool = False
) -> list[str]:
    """Process a single summary file. Returns list of updated entity names."""
    summary_text = summary_path.read_text()
    if not summary_text.strip():
        logger.info("Skipping empty summary for %s", date_str)
        return []

    logger.info("Extracting entities from %s", date_str)
    entities = extract_entities(date_str, summary_text, aliases, config)
    if not entities:
        logger.info("No entities extracted for %s", date_str)
        return []

    updated = []
    for entity in entities:
        name = entity.get("name", "").strip()
        etype = entity.get("type", "").strip()
        facts = entity.get("facts", [])
        relationships = entity.get("relationships", [])
        entity_aliases = entity.get("aliases", [])

        if not name or not etype or etype not in ("person", "project", "course", "organization", "tool"):
            continue

        if not facts:
            continue

        # Resolve to canonical name
        canonical = resolve_entity(name, etype, entity_aliases, aliases)

        # Build relationship lines
        rel_lines = []
        for rel in relationships:
            target = rel.get("target", "")
            target_type = rel.get("target_type", "")
            relation = rel.get("relation", "")
            if target and target_type and relation:
                rel_lines.append(build_relationship_line(target, target_type, relation))

        if dry_run:
            logger.info("  [DRY RUN] Would update %s/%s: %d facts, %d relationships",
                        type_dir(etype), canonical, len(facts), len(rel_lines))
            updated.append(canonical)
            continue

        # Write/update entity page
        path = write_entity_page(canonical, etype, facts, rel_lines, date_str, entity_aliases)
        logger.info("  Updated: %s", path.relative_to(VAULT_PATH))
        updated.append(canonical)

    return updated


def process_note_section(
    date_str: str, section_text: str, aliases: dict, config: dict, dry_run: bool = False
) -> list[str]:
    """Process a single personal note section. Returns list of updated entity names."""
    if not section_text.strip():
        logger.info("Skipping empty note section for %s", date_str)
        return []

    logger.info("Extracting entities from note %s", date_str)
    entities = extract_entities(date_str, section_text, aliases, config)
    if not entities:
        logger.info("No entities extracted from note %s", date_str)
        return []

    updated = []
    for entity in entities:
        name = entity.get("name", "").strip()
        etype = entity.get("type", "").strip()
        facts = entity.get("facts", [])
        relationships = entity.get("relationships", [])
        entity_aliases = entity.get("aliases", [])

        if not name or not etype or etype not in ("person", "project", "course", "organization", "tool"):
            continue

        if not facts:
            continue

        canonical = resolve_entity(name, etype, entity_aliases, aliases)

        rel_lines = []
        for rel in relationships:
            target = rel.get("target", "")
            target_type = rel.get("target_type", "")
            relation = rel.get("relation", "")
            if target and target_type and relation:
                rel_lines.append(build_relationship_line(target, target_type, relation))

        if dry_run:
            logger.info("  [DRY RUN] Would update %s/%s: %d facts, %d relationships",
                        type_dir(etype), canonical, len(facts), len(rel_lines))
            updated.append(canonical)
            continue

        path = write_entity_page(canonical, etype, facts, rel_lines, date_str, entity_aliases)
        logger.info("  Updated: %s", path.relative_to(VAULT_PATH))
        updated.append(canonical)

    return updated


def regenerate_all_truths(aliases: dict, config: dict) -> None:
    """Regenerate compiled truth for all entities that have timeline data."""
    entities = aliases.get("entities", {})
    for key, info in entities.items():
        etype = info.get("type", "")
        canonical = key.split(":", 1)[1] if ":" in key else key
        path = entity_path(canonical, etype)
        if path.exists():
            existing = parse_entity_page(path)
            timeline = existing.get("timeline", "")
            ct = existing.get("compiled_truth", "")
            if timeline and (ct == "*Pending synthesis.*" or ct == ""):
                logger.info("Regenerating compiled truth for %s", canonical)
                regenerate_compiled_truth(canonical, etype, config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entity Graph — extract and maintain entity pages")
    parser.add_argument("--backfill", type=int, metavar="N", help="Process last N days regardless of state")
    parser.add_argument("--seed", action="store_true", help="Seed alias map from known entities")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate compiled truth for all entities")
    parser.add_argument("--notes-only", action="store_true", help="Process only personal handwritten notes")
    args = parser.parse_args()

    load_dotenv(PROJECT_DIR / ".env")
    config = load_raw_config()

    # Seed aliases if requested
    if args.seed:
        aliases = seed_aliases()
        print(f"Seeded {len(aliases['entities'])} entities")
        if not args.backfill and not args.regenerate:
            return
    else:
        aliases = load_aliases()

    # If no entities exist yet, seed automatically
    if not aliases.get("entities"):
        logger.info("No entities found — seeding automatically")
        aliases = seed_aliases()

    # Regenerate compiled truths
    if args.regenerate:
        regenerate_all_truths(aliases, config)
        return

    # Find summaries to process
    state = load_state()
    total_updated = []
    summaries = []

    # --- Process daily summaries (unless --notes-only) ---
    if not args.notes_only:
        if args.backfill:
            summaries = find_summaries(args.backfill)
            logger.info("Backfill mode: %d summaries from last %d days", len(summaries), args.backfill)
        else:
            summaries = find_unprocessed(state)
            logger.info("Found %d unprocessed summaries", len(summaries))

        for date_str, summary_path in summaries:
            try:
                updated = process_summary(date_str, summary_path, aliases, config, dry_run=args.dry_run)
                total_updated.extend(updated)

                if not args.dry_run:
                    state["processed_dates"][date_str] = datetime.now(TZ).isoformat()
                    save_state(state)
                    save_aliases(aliases)

            except Exception:
                logger.exception("Failed to process summary %s", date_str)
                continue

    # --- Process personal handwritten notes ---
    if args.backfill or args.notes_only:
        notes = parse_personal_notes()
        logger.info("Notes backfill: %d note sections found", len(notes))
    else:
        notes = find_unprocessed_notes(state)
        logger.info("Found %d unprocessed note sections", len(notes))

    for date_str, section_text in notes:
        try:
            updated = process_note_section(date_str, section_text, aliases, config, dry_run=args.dry_run)
            total_updated.extend(updated)

            if not args.dry_run:
                state.setdefault("processed_notes_dates", {})[date_str] = datetime.now(TZ).isoformat()
                save_state(state)
                save_aliases(aliases)

        except Exception:
            logger.exception("Failed to process note %s", date_str)
            continue

    if not total_updated:
        print("Nothing to process.")
        return

    # Regenerate compiled truths for updated entities
    if total_updated and not args.dry_run:
        unique_updated = list(set(total_updated))
        logger.info("Regenerating compiled truth for %d updated entities", len(unique_updated))
        entities = aliases.get("entities", {})
        for canonical in unique_updated:
            for key, info in entities.items():
                entity_name = key.split(":", 1)[1] if ":" in key else key
                if entity_name == canonical:
                    regenerate_compiled_truth(canonical, info["type"], config)
                    break

    # Summary
    summary_count = len(summaries) if not args.notes_only else 0
    notes_count = len(notes)
    print(f"Processed {summary_count} summaries + {notes_count} notes, updated {len(total_updated)} entity pages")
    if total_updated:
        unique = sorted(set(total_updated))
        print(f"Entities: {', '.join(unique)}")


if __name__ == "__main__":
    main()

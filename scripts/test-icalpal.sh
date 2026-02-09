#!/bin/bash
# Test icalpal both with and without the wrapper
echo "=== direct ===" > /tmp/icalpal-chain-test.log
icalpal eventsToday -o json > /tmp/icalpal-direct.json 2>> /tmp/icalpal-chain-test.log
echo "direct rc=$? bytes=$(wc -c < /tmp/icalpal-direct.json)" >> /tmp/icalpal-chain-test.log

echo "=== wrapper ===" >> /tmp/icalpal-chain-test.log
/Users/jsperson/.local/bin/digest-wrapper.sh icalpal eventsToday -o json > /tmp/icalpal-wrapper.json 2>> /tmp/icalpal-chain-test.log
echo "wrapper rc=$? bytes=$(wc -c < /tmp/icalpal-wrapper.json)" >> /tmp/icalpal-chain-test.log

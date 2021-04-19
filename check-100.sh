#!/usr/bin/env bash

if ! [ -f testplan ]; then
    echo "testplan missing"
    exit 1
fi

pattern='^[^ ]* \([0-9]*\)$'

non_matching=$(grep -v -e "$pattern" testplan)

if ! [ -z "$non_matching" ]; then
    echo "invalid format for testplan:"
    echo "check for trailing spaces or non-integer case values."
    echo
    echo "$non_matching"
    exit 1
fi

sum=$(sed -s "s/$pattern/\1/g" testplan | paste -s -d + - | bc)

if ! [ $? -eq 0 ]; then
    echo "failed to compute testplan sum"
    exit 1
fi

if ! [ $sum -eq 100 ]; then
    echo "testplan sum mismatch"
    echo "expected 100, got $sum"
fi

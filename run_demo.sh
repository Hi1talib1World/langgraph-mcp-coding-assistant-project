#!/usr/bin/env bash

# Demo Execution Runner Script for ast-healing-coder
# Automatically sets up dependencies, bootstraps a mock workspace, and executes ast-coder self-healing graph.

set -e

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "${BOLD}${CYAN}⚡ AST-HEALING-CODER :: Automated Demo Execution    ${RESET}"
echo -e "${BOLD}${CYAN}====================================================${RESET}\n"

# 1. Check Prerequisites
echo -e "${BOLD}[1/4] Checking Prerequisites...${RESET}"

if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v py &>/dev/null; then
    PYTHON_CMD="py"
else
    echo -e "${YELLOW}Warning: Python 3 not found in PATH.${RESET}"
    exit 1
fi

echo -e "${GREEN}✓ Python: $($PYTHON_CMD --version)${RESET}"

if command -v docker &>/dev/null; then
    echo -e "${GREEN}✓ Docker: $(docker --version)${RESET}"
else
    echo -e "${YELLOW}Notice: Docker CLI not found. Running in isolated fallback subprocess mode.${RESET}"
fi

# 2. Virtual Environment Setup
echo -e "\n${BOLD}[2/4] Setting Up Python Virtual Environment...${RESET}"
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
fi

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

# Install dependencies
pip install -q -e .

echo -e "${GREEN}✓ Package ast-healing-coder installed successfully.${RESET}"

# 3. Create Mock Workspace
echo -e "\n${BOLD}[3/4] Creating Demo Workspace & Buggy Implementation...${RESET}"
mkdir -p demo_workspace/src demo_workspace/tests

cat << 'EOF' > demo_workspace/src/discount.py
import math

def calculate_discount(total: float, discount_percent: float) -> float:
    # Buggy implementation: missing boundary check for discount_percent > 100
    if total < 0 or discount_percent < 0:
        raise ValueError("Invalid total or discount")
    return round(total * (1 - discount_percent / 100), 2)

def calculate_tax(amount: float, tax_rate: float) -> float:
    """Unaffected module function."""
    return round(amount * tax_rate, 2)
EOF

cat << 'EOF' > demo_workspace/tests/test_discount.py
import pytest
from src.discount import calculate_discount

def test_calculate_discount_valid():
    assert calculate_discount(100.0, 20.0) == 80.0

def test_calculate_discount_invalid_over_hundred():
    with pytest.raises(ValueError):
        calculate_discount(100.0, 150.0)
EOF

echo -e "${GREEN}✓ Demo workspace initialized in 'demo_workspace/'.${RESET}"

# 4. Launch AST-Coder Self-Healing Loop
echo -e "\n${BOLD}[4/4] Launching ast-coder Self-Healing Autonomous Loop...${RESET}\n"

ast-coder --demo --request "Fix calculation bug when discount_percent exceeds 100%"

echo -e "\n${BOLD}${GREEN}====================================================${RESET}"
echo -e "${BOLD}${GREEN}✅ Demo Execution Completed Successfully!            ${RESET}"
echo -e "${BOLD}${GREEN}====================================================${RESET}"

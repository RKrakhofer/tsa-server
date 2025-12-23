#!/bin/bash
# Local test runner - runs all tests like GitHub Actions workflow

set -e

echo "=========================================="
echo "TSA Server - Local Test Suite"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠ Warning: No virtual environment activated${NC}"
    echo "Run: source .venv/bin/activate"
    echo ""
fi

# 1. Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -q -r requirements-dev.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# 2. Generate test certificates
echo -e "${YELLOW}🔐 Generating test certificates...${NC}"
mkdir -p certs
python -m tsa.cert_utils --dir certs > /dev/null 2>&1
echo -e "${GREEN}✓ Certificates generated${NC}"
echo ""

# 3. Code formatting check
echo -e "${YELLOW}🎨 Checking code formatting with black...${NC}"
if black --check tsa/ tools/ client/ tests/ 2>/dev/null; then
    echo -e "${GREEN}✓ Code formatting OK${NC}"
else
    echo -e "${RED}✗ Code formatting issues found${NC}"
    echo "Run: black tsa/ tools/ client/ tests/"
    exit 1
fi
echo ""

# 4. Import sorting check
echo -e "${YELLOW}📑 Checking import sorting with isort...${NC}"
if isort --check-only tsa/ tools/ client/ tests/ 2>/dev/null; then
    echo -e "${GREEN}✓ Import sorting OK${NC}"
else
    echo -e "${RED}✗ Import sorting issues found${NC}"
    echo "Run: isort tsa/ tools/ client/ tests/"
    exit 1
fi
echo ""

# 5. Linting
echo -e "${YELLOW}🔍 Linting with flake8...${NC}"
# Critical errors only
if flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics; then
    echo -e "${GREEN}✓ No critical linting errors${NC}"
else
    echo -e "${RED}✗ Critical linting errors found${NC}"
    exit 1
fi

# All errors as warnings
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics > /dev/null
echo ""

# 6. Type checking
echo -e "${YELLOW}🔎 Type checking with mypy...${NC}"
mypy tsa/ --ignore-missing-imports || echo -e "${YELLOW}⚠ Type checking warnings (non-critical)${NC}"
echo ""

# 7. Run pytest
echo -e "${YELLOW}🧪 Running pytest...${NC}"
pytest
echo ""

# 8. Start server and test endpoints
echo -e "${YELLOW}🚀 Testing TSA server startup...${NC}"

# Start server in background
python -m tsa.server --host 127.0.0.1 --port 5000 > /dev/null 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Test health endpoint
if curl -f -s http://127.0.0.1:5000/health > /dev/null; then
    echo -e "${GREEN}✓ Health endpoint OK${NC}"
else
    echo -e "${RED}✗ Health endpoint failed${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

# Test timestamp creation
if echo "test data" | curl -f -s -X POST http://127.0.0.1:5000/tsa --data-binary @- > /dev/null; then
    echo -e "${GREEN}✓ Timestamp creation OK${NC}"
else
    echo -e "${RED}✗ Timestamp creation failed${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

# Cleanup
kill $SERVER_PID 2>/dev/null || true
echo ""

# 9. Test audit chain
echo -e "${YELLOW}⛓️  Testing audit chain functionality...${NC}"
python -c "
from pathlib import Path
from tsa.audit_chain import AuditChain
import tempfile
import os

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db_path = Path(f.name)

try:
    ac = AuditChain(db_path)
    stats = ac.get_statistics()
    assert stats['total_audits'] == 0
    
    export_path = db_path.parent / 'test_export.json'
    ac.export_audit_proof(export_path)
    assert export_path.exists()
    
    print('✓ Audit chain tests passed')
finally:
    if db_path.exists():
        os.unlink(db_path)
    export_path = db_path.parent / 'test_export.json'
    if export_path.exists():
        os.unlink(export_path)
"
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}✓ All tests passed!${NC}"
echo "=========================================="
echo ""
echo "Coverage report: htmlcov/index.html"

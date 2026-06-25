SKILL := plugins/lianhuanhua/skills/lianhuanhua
PYTHON ?= python3

.PHONY: doctor test compile json-check

doctor:
	$(PYTHON) $(SKILL)/scripts/lianhuanhua_cli.py doctor

compile:
	$(PYTHON) -m compileall -q $(SKILL)/scripts

test:
	PYTHONPATH=$(SKILL)/scripts pytest -q $(SKILL)/tests

json-check:
	$(PYTHON) -c "import json; from pathlib import Path; [json.loads(p.read_text(encoding='utf-8')) for p in Path('.').rglob('*.json')]; print('JSON OK')"

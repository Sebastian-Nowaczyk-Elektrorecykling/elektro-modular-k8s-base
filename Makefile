.PHONY: validate render test
validate:
	python3 scripts/validate.py
	bash scripts/check-shell.sh
test:
	python3 -m unittest discover -s tests -v
render:
	bash scripts/render.sh

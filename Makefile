PY ?= python3

.PHONY: help test labs demo clean lint capstone

help:
	@echo "make test      run the unit test suite"
	@echo "make labs      run every lab script in order"
	@echo "make demo      run the agent against this repo"
	@echo "make capstone  run the capstone evals"
	@echo "make lint      compile-check every Python file"
	@echo "make clean     remove caches and scratch output"

test:
	$(PY) -m unittest discover -s tests -t . -v

labs:
	@for f in labs/L*.py; do echo "── $$f"; $(PY) "$$f" || exit 1; done

demo:
	$(PY) -m mini_agent "list the files in this repo" --audit ''

capstone:
	$(PY) -m capstone.repo_doctor --eval

lint:
	$(PY) -m compileall -q mini_agent labs capstone tests

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .mini_agent sandbox .pytest_cache

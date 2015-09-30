pypi:
	python setup.py sdist upload

test:
	tox

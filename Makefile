init:
	LAMBDA_BUILDERS_DEV=1 pip install -e '.[dev]'

test:
	# Run unit tests
	# Fail if coverage falls below 90%
	LAMBDA_BUILDERS_DEV=1 pytest --cov aws_lambda_builders --cov-report term-missing --cov-fail-under 90 tests/unit tests/functional

func-test:
	LAMBDA_BUILDERS_DEV=1 pytest tests/functional

integ-test:
	# Integration tests don't need code coverage
	LAMBDA_BUILDERS_DEV=1 pytest tests/integration

flake:
	# Make sure code conforms to PEP8 standards
	flake8 lambda_builders
	flake8 tests/unit tests/integration

lint:
	# Liner performs static analysis to catch latent bugs
	pylint --rcfile .pylintrc aws_lambda_builders

# Command to run everytime you make changes to verify everything works
dev: flake lint test

# Verifications to run before sending a pull request
pr: init dev

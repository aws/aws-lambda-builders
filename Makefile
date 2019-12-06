init:
	LAMBDA_BUILDERS_DEV=1 pip install -e '.[dev]'

test:
	# Run unit tests
	# Fail if coverage falls below 94%
	LAMBDA_BUILDERS_DEV=1 pytest --cov aws_lambda_builders --cov-report term-missing --cov-fail-under 94 tests/unit tests/functional

func-test:
	LAMBDA_BUILDERS_DEV=1 pytest tests/functional

integ-test:
	# Integration tests don't need code coverage
	LAMBDA_BUILDERS_DEV=1 pytest tests/integration

lint:
	# Liner performs static analysis to catch latent bugs
	pylint --rcfile .pylintrc aws_lambda_builders

# Command to run everytime you make changes to verify everything works
dev: lint test

black:
	black setup.py aws_lambda_builders/* tests/*

black-check:
	black --check setup.py aws_lambda_builders/* tests/*

# Verifications to run before sending a pull request
pr: init dev black-check

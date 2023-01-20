
from unittest import TestCase

from aws_lambda_builders.workflows.rust_cargo.actions import CargoLambdaExecutionException
from aws_lambda_builders.workflows.rust_cargo.cargo_lambda import SubprocessCargoLambda


class TestSubprocessCargoLambda(TestCase):
    def test_raises_RustCargoLambdaBuilderError_if_which_returns_no_results(self):
        def which(cmd, executable_search_paths): return []
        proc = SubprocessCargoLambda(which=which)

        with self.assertRaises(CargoLambdaExecutionException) as raised:
            proc.run("cargo lambda build", "/source_dir")

        self.assertEqual(
            raised.exception.args[0],
            "Cargo Lambda failed: Cannot find Cargo Lambda. Cargo Lambda must be installed on the host machine to use this feature. "
            "Follow the gettings started guide to learn how to install it: https://www.cargo-lambda.info/guide/getting-started.html"
        )

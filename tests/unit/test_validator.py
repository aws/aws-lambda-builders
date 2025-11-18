from unittest import TestCase

from aws_lambda_builders.validator import RuntimeValidator, SUPPORTED_RUNTIMES
from aws_lambda_builders.exceptions import UnsupportedRuntimeError, UnsupportedArchitectureError
from aws_lambda_builders.architecture import ARM64, X86_64
from aws_lambda_builders.supported_runtimes import (
    NODEJS_RUNTIMES,
    PYTHON_RUNTIMES,
    RUBY_RUNTIMES,
    JAVA_RUNTIMES,
    DOTNET_RUNTIMES,
    GO_RUNTIMES,
    CUSTOM_RUNTIMES,
)


class TestRuntimeValidator(TestCase):
    def setUp(self):
        self.validator = RuntimeValidator(runtime="python3.8", architecture="arm64")

    def test_inits(self):
        self.assertEqual(self.validator.runtime, "python3.8")
        self.assertEqual(self.validator.architecture, "arm64")

    def test_validate_runtime(self):
        self.validator.validate("/usr/bin/python3.8")
        self.assertEqual(self.validator._runtime_path, "/usr/bin/python3.8")

    def test_validate_with_case_sensitive_architecture(self):
        """Test that architecture names are case-sensitive"""
        runtime = "python3.12"

        # Test invalid case variations (correct values are "arm64" and "x86_64")
        invalid_arch_cases = ["ARM64", "Arm64", "aRM64", "X86_64", "X86-64", "ARM-64"]
        for arch in invalid_arch_cases:
            with self.subTest(architecture=arch):
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                with self.assertRaises(UnsupportedArchitectureError):
                    validator.validate("/usr/bin/python3.12")

        # Test that correct case works
        for arch in [ARM64, X86_64]:  # These are "arm64" and "x86_64"
            validator = RuntimeValidator(runtime=runtime, architecture=arch)
            result = validator.validate("/usr/bin/python3.12")
            self.assertEqual(result, "/usr/bin/python3.12")

    def test_exception_messages_contain_runtime_info(self):
        """Test that exception messages contain the problematic runtime information"""
        # Test UnsupportedRuntimeError message
        runtime = "unsupported_runtime"
        validator = RuntimeValidator(runtime=runtime, architecture=X86_64)
        with self.assertRaises(UnsupportedRuntimeError) as context:
            validator.validate("/usr/bin/unsupported")

        error_msg = str(context.exception)
        self.assertIn(runtime, error_msg)
        self.assertIn("not supported", error_msg.lower())

        # Test UnsupportedArchitectureError message
        runtime = "python3.12"
        arch = "unsupported_arch"
        validator = RuntimeValidator(runtime=runtime, architecture=arch)
        with self.assertRaises(UnsupportedArchitectureError) as context:
            validator.validate("/usr/bin/python3.12")

        error_msg = str(context.exception)
        self.assertIn(runtime, error_msg)
        self.assertIn(arch, error_msg)
        self.assertIn("not supported", error_msg.lower())

    def test_all_nodejs_runtimes_supported(self):
        """Test all Node.js runtimes are supported with both architectures"""
        for runtime in NODEJS_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/node")
                self.assertEqual(result, "/usr/bin/node")
                self.assertEqual(validator._runtime_path, "/usr/bin/node")

    def test_all_python_runtimes_supported(self):
        """Test all Python runtimes are supported with both architectures"""
        for runtime in PYTHON_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate(f"/usr/bin/{runtime}")
                self.assertEqual(result, f"/usr/bin/{runtime}")
                self.assertEqual(validator._runtime_path, f"/usr/bin/{runtime}")

    def test_all_ruby_runtimes_supported(self):
        """Test all Ruby runtimes are supported with both architectures"""
        for runtime in RUBY_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/ruby")
                self.assertEqual(result, "/usr/bin/ruby")
                self.assertEqual(validator._runtime_path, "/usr/bin/ruby")

    def test_all_java_runtimes_supported(self):
        """Test all Java runtimes are supported with both architectures"""
        for runtime in JAVA_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/java")
                self.assertEqual(result, "/usr/bin/java")
                self.assertEqual(validator._runtime_path, "/usr/bin/java")

    def test_go_runtime_supported(self):
        """Test Go runtime is supported with both architectures"""
        for runtime in GO_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/go")
                self.assertEqual(result, "/usr/bin/go")
                self.assertEqual(validator._runtime_path, "/usr/bin/go")

    def test_all_dotnet_runtimes_supported(self):
        """Test all .NET runtimes are supported with both architectures"""
        for runtime in DOTNET_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/dotnet")
                self.assertEqual(result, "/usr/bin/dotnet")
                self.assertEqual(validator._runtime_path, "/usr/bin/dotnet")

    def test_provided_runtime_supported(self):
        """Test provided runtime is supported with both architectures"""
        for runtime in CUSTOM_RUNTIMES:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/opt/bootstrap")
                self.assertEqual(result, "/opt/bootstrap")
                self.assertEqual(validator._runtime_path, "/opt/bootstrap")

    def test_all_runtimes_support_both_architectures(self):
        """Test that all supported runtimes support both ARM64 and X86_64 architectures"""
        for runtime, supported_archs in SUPPORTED_RUNTIMES.items():
            self.assertIn(ARM64, supported_archs, f"Runtime {runtime} should support ARM64")
            self.assertIn(X86_64, supported_archs, f"Runtime {runtime} should support X86_64")
            self.assertEqual(len(supported_archs), 2, f"Runtime {runtime} should support exactly 2 architectures")

    def test_validate_returns_original_path(self):
        """Test that validate method returns the original runtime_path unchanged"""
        test_cases = [
            ("python3.11", "/usr/local/bin/python3.11"),
            ("nodejs20.x", "/opt/node/bin/node"),
            ("java17", "/usr/lib/jvm/java-17/bin/java"),
            ("provided", "/var/runtime/bootstrap"),
            ("provided.al2", "/var/runtime/bootstrap"),
            ("provided.al2023", "/var/runtime/bootstrap"),
        ]

        for runtime, path in test_cases:
            validator = RuntimeValidator(runtime=runtime, architecture=X86_64)
            result = validator.validate(path)
            self.assertEqual(result, path)
            self.assertEqual(validator._runtime_path, path)

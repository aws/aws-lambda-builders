from unittest import TestCase

from aws_lambda_builders.validator import RuntimeValidator, SUPPORTED_RUNTIMES
from aws_lambda_builders.exceptions import UnsupportedRuntimeError, UnsupportedArchitectureError
from aws_lambda_builders.architecture import ARM64, X86_64


class TestRuntimeValidator(TestCase):
    def setUp(self):
        self.validator = RuntimeValidator(runtime="python3.8", architecture="arm64")

    def test_inits(self):
        self.assertEqual(self.validator.runtime, "python3.8")
        self.assertEqual(self.validator.architecture, "arm64")

    def test_validate_runtime(self):
        self.validator.validate("/usr/bin/python3.8")
        self.assertEqual(self.validator._runtime_path, "/usr/bin/python3.8")

    def test_validate_with_unsupported_runtime(self):
        """Test validation fails for completely unsupported runtimes"""
        unsupported_runtimes = [
            "unknown_runtime",
            "python2.7",  # Legacy Python
            "python3.6",  # Older Python version
            "python3.7",  # Older Python version
            "nodejs12.x",  # Legacy Node.js
            "nodejs14.x",  # Legacy Node.js
            "ruby2.7",  # Legacy Ruby
            "java7",  # Legacy Java
            "dotnet3.1",  # Legacy .NET
            "dotnetcore3.1",  # Legacy .NET Core
            "go1.19",  # Specific Go version (not go1.x)
            "php8.1",  # Unsupported language
            "rust1.0",  # Unsupported language
            "",  # Empty string
        ]

        for runtime in unsupported_runtimes:
            with self.subTest(runtime=runtime):
                validator = RuntimeValidator(runtime=runtime, architecture=X86_64)
                with self.assertRaises(UnsupportedRuntimeError) as context:
                    validator.validate(f"/usr/bin/{runtime}")
                # Verify the error message contains the runtime name
                self.assertIn(runtime, str(context.exception))

    def test_validate_with_runtime_and_incompatible_architecture(self):
        """Test validation fails for unsupported architecture combinations"""
        # Test with various invalid architectures
        invalid_architectures = [
            "invalid_arch",
            "i386",  # 32-bit architecture
            "armv7",  # 32-bit ARM
            "mips",  # Different architecture
            "s390x",  # IBM architecture
            "ppc64le",  # PowerPC
            "aarch32",  # 32-bit ARM variant
            "x86",  # 32-bit x86
            "arm32",  # 32-bit ARM
            "",  # Empty string
            "ARM64",  # Wrong case (should be lowercase)
            "X86_64",  # Wrong case (should be lowercase)
        ]

        # Test with a few different supported runtimes
        test_runtimes = ["python3.12", "nodejs20.x", "java17", "provided"]

        for runtime in test_runtimes:
            for arch in invalid_architectures:
                with self.subTest(runtime=runtime, architecture=arch):
                    validator = RuntimeValidator(runtime=runtime, architecture=arch)
                    with self.assertRaises(UnsupportedArchitectureError) as context:
                        validator.validate(f"/usr/bin/{runtime}")
                    # Verify the error message contains both runtime and architecture
                    error_msg = str(context.exception)
                    self.assertIn(runtime, error_msg)
                    self.assertIn(arch, error_msg)

    def test_validate_with_case_sensitive_runtime(self):
        """Test that runtime names are case-sensitive"""
        case_variants = [
            ("Python3.12", "python3.12"),
            ("PYTHON3.12", "python3.12"),
            ("NodeJS20.x", "nodejs20.x"),
            ("NODEJS20.X", "nodejs20.x"),
            ("Java17", "java17"),
            ("JAVA17", "java17"),
            ("Ruby3.3", "ruby3.3"),
            ("RUBY3.3", "ruby3.3"),
            ("Go1.X", "go1.x"),
            ("GO1.X", "go1.x"),
            ("DotNet8", "dotnet8"),
            ("DOTNET8", "dotnet8"),
            ("Provided", "provided"),
            ("PROVIDED", "provided"),
        ]

        for invalid_case, valid_runtime in case_variants:
            with self.subTest(invalid_case=invalid_case, valid_runtime=valid_runtime):
                # Invalid case should fail
                validator = RuntimeValidator(runtime=invalid_case, architecture=X86_64)
                with self.assertRaises(UnsupportedRuntimeError):
                    validator.validate(f"/usr/bin/{invalid_case}")

                # Valid case should succeed
                validator = RuntimeValidator(runtime=valid_runtime, architecture=X86_64)
                result = validator.validate(f"/usr/bin/{valid_runtime}")
                self.assertEqual(result, f"/usr/bin/{valid_runtime}")

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

    def test_validate_edge_case_runtime_names(self):
        """Test validation with edge case runtime names"""
        edge_case_runtimes = [
            "python3.12.1",  # Version with patch number
            "nodejs20.x.1",  # Version with extra suffix
            "java17-lts",  # Version with suffix
            "python3.12-dev",  # Development version
            "nodejs20",  # Missing .x suffix
            "python3",  # Missing minor version
            "java",  # Missing version number
            "ruby",  # Missing version number
            "go",  # Missing version
            "dotnet",  # Missing version
            "python3.15",  # Future version (not in SUPPORTED_RUNTIMES)
            "nodejs24.x",  # Future version
            "java26",  # Future version
        ]

        for runtime in edge_case_runtimes:
            with self.subTest(runtime=runtime):
                validator = RuntimeValidator(runtime=runtime, architecture=X86_64)
                with self.assertRaises(UnsupportedRuntimeError):
                    validator.validate(f"/usr/bin/{runtime}")

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
        nodejs_runtimes = ["nodejs16.x", "nodejs18.x", "nodejs20.x", "nodejs22.x"]
        for runtime in nodejs_runtimes:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/node")
                self.assertEqual(result, "/usr/bin/node")
                self.assertEqual(validator._runtime_path, "/usr/bin/node")

    def test_all_python_runtimes_supported(self):
        """Test all Python runtimes are supported with both architectures"""
        python_runtimes = [
            "python3.8",
            "python3.9",
            "python3.10",
            "python3.11",
            "python3.12",
            "python3.13",
            "python3.14",
        ]
        for runtime in python_runtimes:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate(f"/usr/bin/{runtime}")
                self.assertEqual(result, f"/usr/bin/{runtime}")
                self.assertEqual(validator._runtime_path, f"/usr/bin/{runtime}")

    def test_all_ruby_runtimes_supported(self):
        """Test all Ruby runtimes are supported with both architectures"""
        ruby_runtimes = ["ruby3.2", "ruby3.3", "ruby3.4"]
        for runtime in ruby_runtimes:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/ruby")
                self.assertEqual(result, "/usr/bin/ruby")
                self.assertEqual(validator._runtime_path, "/usr/bin/ruby")

    def test_all_java_runtimes_supported(self):
        """Test all Java runtimes are supported with both architectures"""
        java_runtimes = ["java8", "java11", "java17", "java21", "java25"]
        for runtime in java_runtimes:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/java")
                self.assertEqual(result, "/usr/bin/java")
                self.assertEqual(validator._runtime_path, "/usr/bin/java")

    def test_go_runtime_supported(self):
        """Test Go runtime is supported with both architectures"""
        runtime = "go1.x"
        for arch in [ARM64, X86_64]:
            validator = RuntimeValidator(runtime=runtime, architecture=arch)
            result = validator.validate("/usr/bin/go")
            self.assertEqual(result, "/usr/bin/go")
            self.assertEqual(validator._runtime_path, "/usr/bin/go")

    def test_all_dotnet_runtimes_supported(self):
        """Test all .NET runtimes are supported with both architectures"""
        dotnet_runtimes = ["dotnet6", "dotnet8"]
        for runtime in dotnet_runtimes:
            for arch in [ARM64, X86_64]:
                validator = RuntimeValidator(runtime=runtime, architecture=arch)
                result = validator.validate("/usr/bin/dotnet")
                self.assertEqual(result, "/usr/bin/dotnet")
                self.assertEqual(validator._runtime_path, "/usr/bin/dotnet")

    def test_provided_runtime_supported(self):
        """Test provided runtime is supported with both architectures"""
        runtime = "provided"
        for arch in [ARM64, X86_64]:
            validator = RuntimeValidator(runtime=runtime, architecture=arch)
            result = validator.validate("/opt/bootstrap")
            self.assertEqual(result, "/opt/bootstrap")
            self.assertEqual(validator._runtime_path, "/opt/bootstrap")

    def test_supported_runtimes_constant_completeness(self):
        """Test that SUPPORTED_RUNTIMES constant includes all expected runtimes"""
        expected_runtimes = {
            # Node.js runtimes
            "nodejs16.x",
            "nodejs18.x",
            "nodejs20.x",
            "nodejs22.x",
            # Python runtimes
            "python3.8",
            "python3.9",
            "python3.10",
            "python3.11",
            "python3.12",
            "python3.13",
            "python3.14",
            # Ruby runtimes
            "ruby3.2",
            "ruby3.3",
            "ruby3.4",
            # Java runtimes
            "java8",
            "java11",
            "java17",
            "java21",
            "java25",
            # Go runtime
            "go1.x",
            # .NET runtimes
            "dotnet6",
            "dotnet8",
            # Provided runtime
            "provided",
        }

        actual_runtimes = set(SUPPORTED_RUNTIMES.keys())
        self.assertEqual(actual_runtimes, expected_runtimes)

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
        ]

        for runtime, path in test_cases:
            validator = RuntimeValidator(runtime=runtime, architecture=X86_64)
            result = validator.validate(path)
            self.assertEqual(result, path)
            self.assertEqual(validator._runtime_path, path)

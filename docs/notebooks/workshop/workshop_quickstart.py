#!/usr/bin/env python3
"""
Weave Workshop - Quick Start Script
Run this to verify your environment is set up correctly.
"""

import os
import sys
from pathlib import Path


def check_imports():
    """Check if required packages are installed"""
    print("🔍 Checking required packages...")

    packages = {
        "weave": "weave",
        "openai": "openai",
        "pydantic": "pydantic",
        "wandb": "wandb",
        "nest_asyncio": "nest_asyncio",
    }

    missing = []
    for package, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is NOT installed")
            missing.append(package)

    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install " + " ".join(missing))
        return False
    return True


def check_wandb_auth():
    """Check W&B authentication status"""
    print("\n🔑 Checking W&B authentication...")

    # Check environment variable
    if os.getenv("WANDB_API_KEY"):
        print("✅ WANDB_API_KEY found in environment")
        return True

    # Check ~/.netrc file
    netrc_path = Path.home() / ".netrc"
    if netrc_path.exists():
        try:
            with open(netrc_path) as f:
                if "api.wandb.ai" in f.read():
                    print("✅ W&B credentials found in ~/.netrc")
                    return True
        except:
            pass

    # W&B will prompt automatically
    print("🟡 No W&B credentials found, but that's OK!")
    print("   Weave will prompt you to log in when needed")
    print("   Get your API key at: https://wandb.ai/authorize")
    return True  # Not a blocking issue


def check_openai_key():
    """Check if OpenAI API key is set"""
    print("\n🔑 Checking OpenAI API key...")

    if os.getenv("OPENAI_API_KEY"):
        print("✅ OPENAI_API_KEY is set")
        return True
    else:
        print("❌ OPENAI_API_KEY is NOT set")
        print("   Set it with: export OPENAI_API_KEY='your-key-here'")
        print("   Get your API key at: https://platform.openai.com/api-keys")
        return False


def test_openai_connection():
    """Test OpenAI API connection"""
    print("\n🤖 Testing OpenAI API connection...")

    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Workshop ready!'"}],
            max_tokens=10,
        )
        print(f"✅ API call successful: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        if "api_key" in str(e).lower():
            print("   Make sure OPENAI_API_KEY is set correctly")
        return False


def test_weave():
    """Test Weave initialization"""
    print("\n📊 Testing Weave setup...")

    try:
        import weave

        # This will use existing auth or prompt if needed
        weave.init("workshop-test")

        @weave.op
        def test_function(x: int) -> int:
            return x * 2

        result = test_function(21)
        print(f"✅ Weave is working! Test result: {result}")
        print("   Check your traces at: https://wandb.ai/home")
        return True
    except Exception as e:
        print(f"❌ Weave test failed: {str(e)}")
        if "WANDB_API_KEY" in str(e):
            print("   Try logging in with: wandb login")
        return False


def main():
    """Run all checks"""
    print("🚀 Weave Workshop - Environment Check\n")

    # Run all checks
    checks_passed = []

    # Check imports
    imports_ok = check_imports()
    checks_passed.append(("Package Installation", imports_ok))

    if not imports_ok:
        print("\n⚠️  Please install missing packages before continuing")
        return 1

    # Check authentication
    wandb_ok = check_wandb_auth()
    checks_passed.append(("W&B Authentication", wandb_ok))

    openai_ok = check_openai_key()
    checks_passed.append(("OpenAI API Key", openai_ok))

    # Test connections (only if keys are available)
    if openai_ok:
        openai_test = test_openai_connection()
        checks_passed.append(("OpenAI Connection", openai_test))

    # Test Weave (will handle auth automatically)
    weave_ok = test_weave()
    checks_passed.append(("Weave Setup", weave_ok))

    # Summary
    print("\n" + "=" * 50)
    print("📋 SUMMARY:")
    print("=" * 50)

    all_passed = all(success for _, success in checks_passed)
    critical_failures = []

    for name, success in checks_passed:
        if name == "W&B Authentication":
            # Special case - show yellow if not found
            status = "✅ READY" if success else "🟡 WILL PROMPT"
        else:
            status = "✅ PASS" if success else "❌ FAIL"
            if not success:
                critical_failures.append(name)
        print(f"{name}: {status}")

    print("=" * 50)

    if all_passed:
        print("\n🎉 All checks passed! You're ready for the workshop!")
        print("\n📝 Next steps:")
        print("1. Open the main workshop file: weave_features_workshop.py")
        print("2. Visit https://wandb.ai/home to see your Weave dashboard")
        print("3. Get ready to build awesome AI applications! 🚀")
    else:
        if not critical_failures:
            print("\n🎉 You're ready for the workshop!")
            print("W&B will prompt for authentication when needed.")
        else:
            print(
                "\n⚠️  Some checks failed. Please fix the issues above before starting the workshop."
            )
            print("\nNeed help? Ask your instructor or check the workshop README.")

    return 0 if not critical_failures else 1


if __name__ == "__main__":
    sys.exit(main())

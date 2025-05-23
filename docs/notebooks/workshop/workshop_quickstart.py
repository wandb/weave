#!/usr/bin/env python3
"""
Weave Workshop - Quick Start Script
Run this to verify your environment is set up correctly.
"""

import os
import sys


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


def check_api_keys():
    """Check if API keys are set"""
    print("\n🔑 Checking API keys...")

    keys_found = True

    if os.getenv("OPENAI_API_KEY"):
        print("✅ OPENAI_API_KEY is set")
    else:
        print("❌ OPENAI_API_KEY is NOT set")
        keys_found = False

    if os.getenv("WANDB_API_KEY"):
        print("✅ WANDB_API_KEY is set")
    else:
        print("❌ WANDB_API_KEY is NOT set")
        print("   Get your API key at: https://wandb.ai/authorize")
        keys_found = False

    return keys_found


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
            print("   Make sure WANDB_API_KEY is set correctly")
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

    # Check API keys
    keys_ok = check_api_keys()
    checks_passed.append(("API Keys", keys_ok))

    # Test OpenAI connection
    openai_ok = test_openai_connection()
    checks_passed.append(("OpenAI Connection", openai_ok))

    # Test Weave
    weave_ok = test_weave()
    checks_passed.append(("Weave Setup", weave_ok))

    # Summary
    print("\n" + "=" * 50)
    print("📋 SUMMARY:")
    print("=" * 50)

    all_passed = True
    for name, success in checks_passed:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name}: {status}")
        if not success:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n🎉 All checks passed! You're ready for the workshop!")
        print("\n📝 Next steps:")
        print("1. Open the main workshop file: weave_features_workshop.py")
        print("2. Visit https://wandb.ai/home to see your Weave dashboard")
        print("3. Get ready to build awesome AI applications! 🚀")
    else:
        print(
            "\n⚠️  Some checks failed. Please fix the issues above before starting the workshop."
        )
        print("\nNeed help? Ask your instructor or check the workshop README.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

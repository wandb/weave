#!/usr/bin/env python3
"""
Prompt Engineering Workshop - Quick Start Script
Run this to verify your environment is set up correctly.
"""

import sys
import subprocess

def check_imports():
    """Check if required packages are installed"""
    print("🔍 Checking required packages...")
    
    packages = {
        'weave': 'weave',
        'openai': 'openai',
        'pydantic': 'pydantic'
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

def check_openai_key():
    """Check if OpenAI API key is set"""
    print("\n🔑 Checking OpenAI API key...")
    
    import os
    if os.environ.get("OPENAI_API_KEY"):
        print("✅ OpenAI API key is set")
        return True
    else:
        print("❌ OpenAI API key is NOT set")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return False

def test_basic_call():
    """Test a basic OpenAI API call"""
    print("\n🤖 Testing OpenAI API connection...")
    
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Workshop ready!'"}],
            max_tokens=10
        )
        print(f"✅ API call successful: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        return False

def test_weave():
    """Test Weave initialization"""
    print("\n📊 Testing Weave setup...")
    
    try:
        import weave
        weave.init("workshop_test")
        
        @weave.op
        def test_function(x: int) -> int:
            return x * 2
        
        result = test_function(21)
        print(f"✅ Weave is working! Test result: {result}")
        return True
    except Exception as e:
        print(f"❌ Weave test failed: {str(e)}")
        return False

def main():
    """Run all checks"""
    print("🚀 Prompt Engineering Workshop - Environment Check\n")
    
    checks = [
        ("Package Installation", check_imports),
        ("OpenAI API Key", check_openai_key),
        ("API Connection", test_basic_call),
        ("Weave Setup", test_weave)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            success = check_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} check failed with error: {str(e)}")
            results.append((name, False))
    
    print("\n" + "="*50)
    print("📋 SUMMARY:")
    print("="*50)
    
    all_passed = True
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name}: {status}")
        if not success:
            all_passed = False
    
    print("="*50)
    
    if all_passed:
        print("\n🎉 All checks passed! You're ready for the workshop!")
        print("\n📝 Next steps:")
        print("1. Open the workshop notebook: prompt_engineering_workshop_complete.ipynb")
        print("2. Visit https://wandb.ai/home to see your Weave dashboard")
        print("3. Get ready to build awesome prompts! 🚀")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above before starting the workshop.")
        print("\nNeed help? Ask your instructor or check the workshop README.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main()) 
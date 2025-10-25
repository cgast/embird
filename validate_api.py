"""Quick validation script to test API schemas and imports."""

import sys
import traceback

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    try:
        from app.schemas import (
            ErrorResponse,
            SuccessResponse,
            NewsItemResponse,
            NewsItemSimilarity,
            URLResponse,
            PreferenceVectorResponse
        )
        print("✓ All schemas imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        traceback.print_exc()
        return False

def test_schema_validation():
    """Test that schemas work correctly."""
    print("\nTesting schema validation...")

    try:
        from app.schemas.common import ErrorResponse, SuccessResponse
        from app.schemas.url import URLCreate
        from app.schemas.news import NewsSearchRequest

        # Test ErrorResponse
        error = ErrorResponse(detail="Test error")
        assert error.detail == "Test error"
        print("✓ ErrorResponse works")

        # Test SuccessResponse
        success = SuccessResponse(success=True, message="Test")
        assert success.success == True
        print("✓ SuccessResponse works")

        # Test URLCreate with validation
        url_create = URLCreate(url="https://example.com/rss", type="rss")
        assert url_create.url == "https://example.com/rss"
        assert url_create.type == "rss"
        print("✓ URLCreate validation works")

        # Test NewsSearchRequest
        search = NewsSearchRequest(query="AI news", limit=10)
        assert search.query == "AI news"
        assert search.limit == 10
        print("✓ NewsSearchRequest works")

        # Test invalid URL (should raise ValidationError)
        try:
            invalid_url = URLCreate(url="not-a-url", type="rss")
            print("✗ URL validation failed - should have raised error")
            return False
        except Exception:
            print("✓ URL validation correctly rejects invalid URLs")

        return True

    except Exception as e:
        print(f"✗ Schema validation error: {e}")
        traceback.print_exc()
        return False

def test_api_routes():
    """Test that API routes can be imported."""
    print("\nTesting API routes...")

    try:
        from app.routes.api import router
        print(f"✓ API router imported successfully")
        print(f"  Router has {len(router.routes)} routes")

        # List all routes
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ','.join(route.methods) if route.methods else 'N/A'
                print(f"  - [{methods}] {route.path}")

        return True
    except Exception as e:
        print(f"✗ API routes error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("EmBird API Validation")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Schema Validation", test_schema_validation()))
    results.append(("API Routes", test_api_routes()))

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

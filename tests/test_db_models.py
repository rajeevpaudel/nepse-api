def test_models_importable():
    from db.models import Security, NepseToken
    assert Security.__tablename__ == "securities"
    assert NepseToken.__tablename__ == "nepse_token"

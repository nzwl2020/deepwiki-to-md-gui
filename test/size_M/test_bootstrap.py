from src.interface.bootstrap import build_usecases


def test_build_usecases_returns_chat_and_wiki():
    usecases = build_usecases()

    assert "chat" in usecases
    assert "wiki" in usecases

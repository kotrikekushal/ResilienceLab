from backend.security.password import (
    hash_password,
    verify_password,
)


def test_password_hashing():
    password = "StrongPassword@123"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert isinstance(hashed_password, str)


def test_correct_password_verification():
    password = "StrongPassword@123"

    hashed_password = hash_password(password)

    assert verify_password(
        password,
        hashed_password,
    ) is True


def test_wrong_password_verification():
    password = "StrongPassword@123"
    wrong_password = "WrongPassword@123"

    hashed_password = hash_password(password)

    assert verify_password(
        wrong_password,
        hashed_password,
    ) is False


def test_same_password_generates_different_hashes():
    password = "StrongPassword@123"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash

    assert verify_password(password, first_hash) is True
    assert verify_password(password, second_hash) is True
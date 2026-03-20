from unittest.mock import MagicMock


def mock_scalar_result(return_value):
    """Simulates session.execute().scalars().first()"""
    return MagicMock(
        scalars=MagicMock(
            return_value=MagicMock(first=MagicMock(return_value=return_value))
        )
    )


def mock_scalar_one_or_none(return_value):
    """Simulates session.execute().scalar_one_or_none()"""
    return MagicMock(scalar_one_or_none=MagicMock(return_value=return_value))


def mock_scalars_all(return_value: list):
    """Simulates session.execute().scalars().all()"""
    return MagicMock(
        scalars=MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=return_value))
        )
    )

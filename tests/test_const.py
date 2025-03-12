from process_dcm.const import ImageModality


def test_str() -> None:
    assert str(ImageModality.COLOUR_PHOTO) == "Colour Photo"
    assert str(ImageModality.SLO_RED) == "SLO - Red"
    assert str(ImageModality.FACE_PHOTO) == "Face photo"


def test_is_colour() -> None:
    assert ImageModality.COLOUR_PHOTO.is_colour is True
    assert ImageModality.INFRARED_PHOTO.is_colour is False
    assert ImageModality.SLO_RED.is_colour is False
    assert ImageModality.REFLECTANCE_MCOLOR.is_colour is False


def test_is_2d_image() -> None:
    assert ImageModality.COLOUR_PHOTO.is_2d_image is True
    assert ImageModality.INFRARED_PHOTO.is_2d_image is True
    assert ImageModality.SLO_RED.is_2d_image is True
    assert ImageModality.OCT.is_2d_image is False


def test_is_sensitive() -> None:
    assert ImageModality.FACE_PHOTO.is_sensitive is True
    assert ImageModality.SLO_RED.is_sensitive is False
    assert ImageModality.ENCAPSULATED_PDF.is_sensitive is True
    assert ImageModality.UNKNOWN.is_sensitive is True

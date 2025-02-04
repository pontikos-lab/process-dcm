"""constant classes."""

from enum import Enum, Flag, auto, unique
from typing import cast

RESERVED_CSV = "study_2_patient.csv"


class ModalityFlag(Flag):
    """A flag representing different modalities in DICOM files."""

    NONE = 0
    IS_COLOUR = auto()
    IS_2D_IMAGE = auto()
    # We can use modalities to guess whether certain images are exterior/anterior
    IS_ANTERIOR = auto()
    IS_INTERIOR = auto()
    # Images which could contain sensitive data, e.g. face photos, or identifiable text
    SENSITIVE = auto()


@unique
class ImageModality(Enum):
    """An enumeration of different modalities in DICOM files."""

    COLOUR_PHOTO = ("CP", "Colour Photo", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_COLOUR)
    INFRARED_PHOTO = ("IRP", "Infrared Photo", ModalityFlag.IS_2D_IMAGE)

    # Scanning laser ophthalmoscopy.
    SLO_RED = ("SLO_R", "SLO - Red", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    SLO_GREEN = ("SLO_G", "SLO - Green", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    SLO_BLUE = ("SLO_B", "SLO - Blue", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    SLO_INFRARED = ("SLO_IR", "SLO - Infrared", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    SLO_INFRARED_CROSS_POLARIZED = (
        "SLO_IR_XP",
        "SLO - Infrared (cross-polarized)",
        ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR,
    )

    FLUORESCEIN_ANGIOGRAPHY = ("FA", "FA", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    INDOCYANINE_GREEN_ANGIOGRAPHY = ("ICGA", "ICGA", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    RED_FREE = ("RF", "Red-free", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    RED_FREE_CROSS_POLARIZED = (
        "RF_XP",
        "Red-free (cross-polarized)",
        ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR,
    )
    FA_ICGA = ("FA+ICGA", "FA+ICGA", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)

    AUTOFLUORESCENCE_BLUE = ("AF_B", "AF - Blue", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    AUTOFLUORESCENCE_GREEN = ("AF_G", "AF - Green", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)
    AUTOFLUORESCENCE_IR = ("AF_IR", "AF - Infrared", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)

    REFLECTANCE_RED = ("REF_R", "Reflectance - Red", ModalityFlag.IS_2D_IMAGE)
    REFLECTANCE_GREEN = ("REF_G", "Reflectance - Green", ModalityFlag.IS_2D_IMAGE)
    REFLECTANCE_BLUE = ("REF_B", "Reflectance - Blue", ModalityFlag.IS_2D_IMAGE)
    REFLECTANCE_BLUE_CROSS_POLARIZED = ("REF_B_XP", "Reflectance - Blue (cross-polarized)", ModalityFlag.IS_2D_IMAGE)
    REFLECTANCE_IR = ("REF_IR", "Reflectance - Infrared", ModalityFlag.IS_2D_IMAGE)
    REFLECTANCE_MCOLOR = ("MCR", "Multi Color Reflectance - RGB", ModalityFlag.IS_2D_IMAGE)  # REF_R + REF_G + REF_B

    OCT = ("OCT", "OCT")

    CORNEA_MICROSCOPY = ("CM", "Cornea Microscopy")
    MPOD = ("MPOD", "MP Optical Density")

    HR_TOMOGRAPHY = ("HRT", "HR Tomography")

    SLIT_LAMP = ("SLIT", "Slit Lamp", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_ANTERIOR)
    RED = ("RED", "Red", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)

    FACE_PHOTO = ("FACE", "Face photo", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_ANTERIOR | ModalityFlag.SENSITIVE)

    PSEUDOCOLOUR_ULTRAWIDEFIELD = (
        "PCUWF",
        "Pseudocolour Ultra-widefield",
        ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR | ModalityFlag.IS_COLOUR,
    )

    OPTOS_FA = ("OPTOS_FA", "Optos Ultra-Widefield FA", ModalityFlag.IS_2D_IMAGE | ModalityFlag.IS_INTERIOR)

    # VF-related modalities
    FDF = ("FDF", "Flicker Defined Form Perimetry")
    SAP = ("SAP", "Standard Automated Perimetry")

    # Values which are not real images or may contain sensitive data.
    # Librarian will want to ignore these
    MPOD_RESULT = ("MPODR", "MP Optical Density Result")
    THICKNESS = ("T", "Thickness")
    CELL_ANALYSIS = ("CELL", "Cell Analysis")
    ENCAPSULATED_PDF = ("PDF", "PDF", ModalityFlag.SENSITIVE)

    # Mark this as 'sensitive' as we just don't know what data could be in here
    UNKNOWN = ("U", "Unknown", ModalityFlag.SENSITIVE)

    flags: ModalityFlag
    code: str

    def __new__(cls, code: str, description: str, flags: ModalityFlag = ModalityFlag.NONE) -> "ImageModality":
        """Create a new instance of the ImageModality enum class.

        Args:
            code (str): The modality code.
            description (str): A description of the modality.
            flags (ModalityFlag, optional): Any additional flags for the modality. Defaults to ModalityFlag.NONE.

        Returns:
            ImageModality: An instance of the ImageModality class.
        """
        # This is the canonical way of overriding handling of the enum value.
        # See https://docs.python.org/3/library/enum.html#using-a-custom-new
        obj = object.__new__(cls)
        # Use the long-form as the value as it is likely to be more useful than the short-hand code
        obj._value_ = description
        obj.code = code
        obj.flags = flags
        return obj

    def __str__(self) -> str:
        """Return the modality code."""
        return cast(str, self.value)

    @property
    def is_colour(self) -> bool:
        """Returns True if this modality contains colour data."""
        return ModalityFlag.IS_COLOUR in self.flags

    @property
    def is_2d_image(self) -> bool:
        """Returns True if this modality contains 2D image data."""
        return ModalityFlag.IS_2D_IMAGE in self.flags

    @property
    def is_sensitive(self) -> bool:
        """Returns True if this modality may contain sensitive data."""
        return ModalityFlag.SENSITIVE in self.flags

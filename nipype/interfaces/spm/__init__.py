"""Top-level namespace for spm."""

from nipype.interfaces.spm.base import (SpmInfo, SpmMatlabCommandLine,
                                        scans_for_fname, scans_for_fnames)
from nipype.interfaces.spm.preprocess import (SliceTiming, Realign, Coregister,
                                              Normalize, Segment, Smooth)
from nipype.interfaces.spm.model import (Level1Design, EstimateModel,
                                         EstimateContrast, OneSampleTTest,
                                         TwoSampleTTest, MultipleRegression)

# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
A pipeline example that intergrates spm, fsl freesurfer modules to perform a
comparative volume and surface based first level analysis.

This tutorial uses the nipype-tutorial data and hence should be run from the
directory containing tutorial data

    python freesurfer_tutorial.py

"""

import os                                    # system functions

import nipype.algorithms.modelgen as model   # model generation
import nipype.algorithms.rapidart as ra      # artifact detection
import nipype.interfaces.freesurfer as fs    # freesurfer
import nipype.interfaces.io as nio           # i/o routines
import nipype.interfaces.matlab as mlab      # how to run matlab
import nipype.interfaces.spm as spm          # spm
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine

"""
Preliminaries
-------------

Confirm package dependencies are installed.  (This is only for the tutorial,
rarely would you put this in your own code.) 
"""

from nipype.utils.misc import package_check

package_check('numpy', '1.3', 'tutorial1')
package_check('scipy', '0.7', 'tutorial1')
package_check('networkx', '1.0', 'tutorial1')
package_check('IPython', '0.10', 'tutorial1')

"""Set any package specific configuration.

Setting the subjects directory and the appropriate matlab command to use. if
you want to use a different spm version/path, it should also be entered here.

These are currently being set at the class level, so every node will inherit
these settings. However, these can also be changed or set for an individual
node. 
"""

# Tell freesurfer what subjects directory to use
subjects_dir = os.path.abspath('fsdata')
fs.FSCommand.set_default_subjects_dir(subjects_dir)

# Set the way matlab should be called
mlab.MatlabCommand.set_default_matlab_cmd("matlab -nodesktop -nosplash")
# If SPM is not in your MATLAB path you should add it here
# mlab.MatlabCommand.set_default_paths('/path/to/your/spm8')


"""
Setup preprocessing workflow
----------------------------


"""

preproc = pe.Workflow(name='preproc')


"""
Use :class:`nipype.interfaces.spm.Realign` for motion correction
and register all images to the mean image.
"""

realign = pe.Node(interface=spm.Realign(), name="realign")
realign.inputs.register_to_mean = True

"""
Use :class:`nipype.algorithms.rapidart` to determine which of the
images in the functional series are outliers based on deviations in
intensity or movement.
"""

art = pe.Node(interface=ra.ArtifactDetect(), name="art")
art.inputs.use_differences      = [False,True]
art.inputs.use_norm             = True
art.inputs.norm_threshold       = 0.5
art.inputs.zintensity_threshold = 3
art.inputs.mask_type            = 'file'
art.inputs.parameter_source     = 'SPM'

"""
Use :class:`nipype.interfaces.freesurfer.BBRegister` to coregister the mean
functional image generated by realign to the subjects' surfaces.
"""

surfregister = pe.Node(interface=fs.BBRegister(),name='surfregister')
surfregister.inputs.init = 'fsl'
surfregister.inputs.contrast_type = 't2'

"""
Use :class:`nipype.interfaces.io.FreeSurferSource` to retrieve various image
files that are automatically generated by the recon-all process.
"""

FreeSurferSource = pe.Node(interface=nio.FreeSurferSource(), name='fssource')

"""
Use :class:`nipype.interfaces.freesurfer.ApplyVolTransform` to convert the
brainmask generated by freesurfer into the realigned functional space.
"""

ApplyVolTransform = pe.Node(interface=fs.ApplyVolTransform(),
                            name='applyreg')
ApplyVolTransform.inputs.inverse = True 

"""
Use :class:`nipype.interfaces.freesurfer.Binarize` to extract a binary brain
mask.
"""

Threshold = pe.Node(interface=fs.Binarize(),name='threshold')
Threshold.inputs.min = 10
Threshold.inputs.out_type = 'nii'

"""
Two different types of functional data smoothing are performed in this
workflow. The volume smoothing option performs a standard SPM smoothin. using
:class:`nipype.interfaces.spm.Smooth`. In addition, we use a smoothing routine
from freesurfer (:class:`nipype.interfaces.freesurfer.Binarize`) to project the
functional data from the volume to the subjects' surface, smooth it on the
surface and fit it back into the volume forming the cortical ribbon. The
projection uses the average value along a "cortical column". In addition to the
surface smoothing, the rest of the volume is smoothed with a 3d gaussian kernel.

.. note::

    It is very important to note that the projection to the surface takes a 3d
    manifold to a 2d manifold. Hence the reverse projection, simply fills the
    thickness of cortex with the smoothed data. The smoothing is not performed
    in a depth specific manner. The output of this branch should only be used
    for surface-based analysis and visualization.
    
"""

volsmooth = pe.Node(interface=spm.Smooth(), name = "volsmooth")
surfsmooth = pe.MapNode(interface=fs.Smooth(proj_frac_avg=(0,1,0.1)), name = "surfsmooth",
                        iterfield=['in_file'])

"""
We connect up the different nodes to implement the preprocessing workflow.
"""

preproc.connect([(realign, surfregister,[('mean_image', 'source_file')]),
                 (FreeSurferSource, ApplyVolTransform,[('brainmask','target_file')]),
                 (surfregister, ApplyVolTransform,[('out_reg_file','reg_file')]),
                 (realign, ApplyVolTransform,[('mean_image', 'source_file')]),
                 (ApplyVolTransform, Threshold,[('transformed_file','in_file')]),
                 (realign, art,[('realignment_parameters','realignment_parameters'),
                               ('realigned_files','realigned_files')]),
                 (Threshold, art, [('binary_file', 'mask_file')]),
                 (realign, volsmooth, [('realigned_files', 'in_files')]),
                 (realign, surfsmooth, [('realigned_files', 'in_file')]),
                 (surfregister, surfsmooth, [('out_reg_file','reg_file')]),
                 ])


"""
Set up volume analysis workflow
-------------------------------

"""

volanalysis = pe.Workflow(name='volanalysis')

"""
Generate SPM-specific design information using
:class:`nipype.interfaces.spm.SpecifyModel`.
"""

modelspec = pe.Node(interface=model.SpecifyModel(), name= "modelspec")
modelspec.inputs.concatenate_runs        = True

"""
Generate a first level SPM.mat file for analysis
:class:`nipype.interfaces.spm.Level1Design`.
"""

level1design = pe.Node(interface=spm.Level1Design(), name= "level1design")
level1design.inputs.bases              = {'hrf':{'derivs': [0,0]}}

"""
Use :class:`nipype.interfaces.spm.EstimateModel` to determine the
parameters of the model.
"""

level1estimate = pe.Node(interface=spm.EstimateModel(), name="level1estimate")
level1estimate.inputs.estimation_method = {'Classical' : 1}

"""
Use :class:`nipype.interfaces.spm.EstimateContrast` to estimate the
first level contrasts specified in a few steps above.
"""

contrastestimate = pe.Node(interface = spm.EstimateContrast(), name="contrastestimate")

volanalysis.connect([(modelspec,level1design,[('session_info','session_info')]),
                  (level1design,level1estimate,[('spm_mat_file','spm_mat_file')]),
                  (level1estimate,contrastestimate,[('spm_mat_file','spm_mat_file'),
                                                  ('beta_images','beta_images'),
                                                  ('residual_image','residual_image')]),
                  ])

"""
Set up surface analysis workflow
--------------------------------

We simply clone the volume analysis workflow.
"""

surfanalysis = volanalysis.clone(name='surfanalysis')


"""
Set up volume normalization workflow
------------------------------------

The volume analysis is performed in individual space. Therefore, post analysis
we normalize the contrast images to MNI space.
"""

volnorm = pe.Workflow(name='volnormconimages')

"""
Use :class:`nipype.interfaces.freesurfer.MRIConvert` to convert the brainmask,
an mgz file and the contrast images (nifti-1 img/hdr pairs), to single volume
nifti images.
"""

convert = pe.Node(interface=fs.MRIConvert(out_type='nii'),name='convert2nii')
convert2 = pe.MapNode(interface=fs.MRIConvert(out_type='nii'),
                      iterfield=['in_file'],
                      name='convertimg2nii')

"""
Use :class:`nipype.interfaces.spm.Segment` to segment the structural image and
generate the transformation file to MNI space.

.. note::

   Segment takes longer than usual because the nose is wrapped behind
   the head in the structural image.
"""

segment = pe.Node(interface=spm.Segment(), name='segment')

"""
Use :class:`nipype.interfaces.freesurfer.ApplyVolTransform` to convert contrast
images into freesurfer space.
"""

normwreg = pe.MapNode(interface=fs.ApplyVolTransform(),
                      iterfield=['source_file'],
                      name='applyreg2con')

"""
Use :class:`nipype.interfaces.spm.Normalize` to normalize the contrast images
to MNI space
"""

normalize = pe.Node(interface=spm.Normalize(jobtype='write'),
                    name='norm2mni')

"""
Connect up the volume normalization components
"""

volnorm.connect([(convert, segment, [('out_file','data')]),
                 (convert2, normwreg, [('out_file', 'source_file')]),
                 (segment, normalize, [('transformation_mat', 'parameter_file')]),
                 (normwreg, normalize, [('transformed_file','apply_to_files')]),
                 ])

"""
Preproc + Analysis + VolumeNormalization workflow
-------------------------------------------------

Connect up the lower level workflows into an integrated analysis. In addition,
we add an input node that specifies all the inputs needed for this
workflow. Thus, one can import this workflow and connect it to their own data
sources. An example with the nifti-tutorial data is provided below.

For this workflow the only necessary inputs are the functional images, a
freesurfer subject id corresponding to recon-all processed data, the session
information for the functional runs and the contrasts to be evaluated.
"""

inputnode = pe.Node(interface=util.IdentityInterface(fields=['func',
                                                             'subject_id',
                                                             'session_info',
                                                             'contrasts']),
                    name='inputnode')

"""
Connect the components into an integrated workflow.
"""

l1pipeline = pe.Workflow(name='firstlevel')
l1pipeline.connect([(inputnode,preproc,[('func','realign.in_files'),
                                        ('subject_id','surfregister.subject_id'),
                                        ('subject_id','fssource.subject_id'),
                                        ]),
                    (inputnode, volanalysis,[('subject_id','modelspec.subject_id'),
                                             ('session_info','modelspec.subject_info'),
                                             ('contrasts','contrastestimate.contrasts')]),
                    (inputnode, surfanalysis,[('subject_id','modelspec.subject_id'),
                                              ('session_info','modelspec.subject_info'),
                                              ('contrasts','contrastestimate.contrasts')]),
                    ])

# attach volume and surface model specification and estimation components
l1pipeline.connect([(preproc, volanalysis, [('realign.realignment_parameters',
                                            'modelspec.realignment_parameters'),
                                           ('volsmooth.smoothed_files',
                                            'modelspec.functional_runs'),
                                           ('art.outlier_files',
                                            'modelspec.outlier_files'),
                                           ('threshold.binary_file',
                                            'level1design.mask_image')]),
                    (preproc, surfanalysis, [('realign.realignment_parameters',
                                              'modelspec.realignment_parameters'),
                                             ('surfsmooth.smoothed_file',
                                              'modelspec.functional_runs'),
                                             ('art.outlier_files',
                                              'modelspec.outlier_files'),
                                             ('threshold.binary_file',
                                              'level1design.mask_image')])
                    ])

# attach volume contrast normalization components
l1pipeline.connect([(preproc, volnorm, [('fssource.orig','convert2nii.in_file'),
                                        ('surfregister.out_reg_file','applyreg2con.reg_file'),
                                        ('fssource.orig','applyreg2con.target_file')]),
                    (volanalysis, volnorm, [('contrastestimate.con_images',
                                             'convertimg2nii.in_file'),
                                            ])
                  ])


"""
Data specific components
------------------------

The nipype tutorial contains data for two subjects.  Subject data
is in two subdirectories, ``s1`` and ``s2``.  Each subject directory
contains four functional volumes: f3.nii, f5.nii, f7.nii, f10.nii. And
one anatomical volume named struct.nii.

Below we set some variables to inform the ``datasource`` about the
layout of our data.  We specify the location of the data, the subject
sub-directories and a dictionary that maps each run to a mnemonic (or
field) for the run type (``struct`` or ``func``).  These fields become
the output fields of the ``datasource`` node in the pipeline.

In the example below, run 'f3' is of type 'func' and gets mapped to a
nifti filename through a template '%s.nii'. So 'f3' would become
'f3.nii'.

"""

# Specify the location of the data.
data_dir = os.path.abspath('data')
# Specify the subject directories
subject_list = ['s1', 's3']
# Map field names to individual subject runs.
info = dict(func=[['subject_id', ['f3','f5','f7','f10']]],
            struct=[['subject_id','struct']])

infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id']), name="infosource")

"""Here we set up iteration over all the subjects. The following line
is a particular example of the flexibility of the system.  The
``datasource`` attribute ``iterables`` tells the pipeline engine that
it should repeat the analysis on each of the items in the
``subject_list``. In the current example, the entire first level
preprocessing and estimation will be repeated for each subject
contained in subject_list.
"""

infosource.iterables = ('subject_id', subject_list)

"""
Now we create a :class:`nipype.interfaces.io.DataGrabber` object and
fill in the information from above about the layout of our data.  The
:class:`nipype.pipeline.NodeWrapper` module wraps the interface object
and provides additional housekeeping and pipeline specific
functionality.
"""

datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                               outfields=['func', 'struct']),
                     name = 'datasource')
datasource.inputs.base_directory = data_dir
datasource.inputs.template = '%s/%s.nii'
datasource.inputs.template_args = info


"""
Set preprocessing parameters
----------------------------
"""

l1pipeline.inputs.preproc.fssource.subjects_dir = subjects_dir
l1pipeline.inputs.preproc.volsmooth.fwhm = 4
l1pipeline.inputs.preproc.surfsmooth.surface_fwhm = 5
l1pipeline.inputs.preproc.surfsmooth.vol_fwhm = 4


"""
Experimental paradigm specific components
-----------------------------------------

Here we create a function that returns subject-specific information
about the experimental paradigm. This is used by the
:class:`nipype.interfaces.spm.SpecifyModel` to create the information
necessary to generate an SPM design matrix. In this tutorial, the same
paradigm was used for every participant.
"""

from nipype.interfaces.base import Bunch
from copy import deepcopy
def subjectinfo(subject_id):
    print "Subject ID: %s\n"%str(subject_id)
    output = []
    names = ['Task-Odd','Task-Even']
    for r in range(4):
        onsets = [range(15,240,60),range(45,240,60)]
        output.insert(r,
                      Bunch(conditions=names,
                            onsets=deepcopy(onsets),
                            durations=[[15] for s in names],
                            amplitudes=None,
                            tmod=None,
                            pmod=None,
                            regressor_names=None,
                            regressors=None))
    return output

"""Setup the contrast structure that needs to be evaluated. This is a
list of lists. The inner list specifies the contrasts and has the
following format - [Name,Stat,[list of condition names],[weights on
those conditions]. The condition names must match the `names` listed
in the `subjectinfo` function described above.
"""

cont1 = ('Task>Baseline','T', ['Task-Odd','Task-Even'],[0.5,0.5])
cont2 = ('Task-Odd>Task-Even','T', ['Task-Odd','Task-Even'],[1,-1])
contrasts = [cont1,cont2]

"""
Set up node specific inputs
---------------------------

We replicate the modelspec parameters separately for the surface- and
volume-based analysis.
"""

modelspecref = l1pipeline.inputs.volanalysis.modelspec
modelspecref.input_units             = 'secs'
modelspecref.output_units            = 'secs'
modelspecref.time_repetition         = 3.
modelspecref.high_pass_filter_cutoff = 120

modelspecref = l1pipeline.inputs.surfanalysis.modelspec
modelspecref.input_units             = 'secs'
modelspecref.output_units            = 'secs'
modelspecref.time_repetition         = 3.
modelspecref.high_pass_filter_cutoff = 120

l1designref = l1pipeline.inputs.volanalysis.level1design
l1designref.timing_units       = modelspecref.output_units
l1designref.interscan_interval = modelspecref.time_repetition

l1designref = l1pipeline.inputs.surfanalysis.level1design
l1designref.timing_units       = modelspecref.output_units
l1designref.interscan_interval = modelspecref.time_repetition

l1pipeline.inputs.inputnode.contrasts = contrasts


"""
Setup the pipeline
------------------

The nodes created above do not describe the flow of data. They merely
describe the parameters used for each function. In this section we
setup the connections between the nodes such that appropriate outputs
from nodes are piped into appropriate inputs of other nodes.

Use the :class:`nipype.pipeline.engine.Workfow` to create a
graph-based execution pipeline for first level analysis. 
"""

level1 = pe.Workflow(name="level1")
level1.base_dir = os.path.abspath('volsurf_tutorial/workingdir')

level1.connect([(infosource, datasource, [('subject_id', 'subject_id')]),
                (datasource,l1pipeline,[('func','inputnode.func')]),
                (infosource,l1pipeline,[('subject_id','inputnode.subject_id'),
                                       (('subject_id', subjectinfo),
                                        'inputnode.session_info')]),
                ])

"""
Run the analysis pipeline and also create a dot+png (if graphviz is available)
that visually represents the workflow.
"""

if __name__ == '__main__':
    level1.run()
    level1.write_graph(graph2use='flat')


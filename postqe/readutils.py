#!/usr/bin/env python3
#encoding: UTF-8

"""
A collection of functions for reading different files and quantities.
"""

import numpy as np
import h5py
from xml.etree import ElementTree as ET


def read_charge_file_hdf5(filename, nr):
    """
    Reads a charge file written with QE in HDF5 format. *nr = [nr1,nr2,nr3]* (the dimensions of
    the charge k-points grid) are given as parameter (taken for the xml output file by the caller).

    Notes: In the new format, the values of the charge in the reciprocal space are stored.
    Besides, only the values of the charge > cutoff are stored, together with the Miller indexes.
    Hence
    """

    nr1, nr2, nr3 = nr
    with h5py.File(filename, "r") as h5f:
        ngm_g = h5f.attrs.get('ngm_g')
        # Read the total charge
        aux = np.array(h5f['rhotot_g']).reshape([ngm_g,2])
        rhotot_g = np.array(list(map(lambda x: x.dot((1e0,1.j)), aux)))
        rho_temp = np.zeros([nr1,nr2,nr3],dtype=np.complex128)
        for el in zip( h5f['MillerIndices'],rhotot_g):
            (i,j,k), rho = el
            rho_temp[i,j,k]=rho
        rhotot_r = np.fft.ifftn(rho_temp) * nr1 * nr2 * nr3

        # Read the charge difference spin up - spin down if present (for magnetic calculations)
        try:
            aux = np.array(h5f['rhodiff_g']).reshape([ngm_g, 2])
            rhodiff_g = np.array(list(map(lambda x: x.dot((1e0, 1.j)), aux)))
            rho_temp = np.zeros([nr1, nr2, nr3], dtype=np.complex128)
            for el in zip(h5f['MillerIndices'], rhodiff_g):
                (i, j, k), rho = el
                rho_temp[i, j, k] = rho
            rhodiff_r = np.fft.ifftn(rho_temp) * nr1 * nr2 * nr3
        except:
            rhodiff_r = np.zeros([nr1, nr2, nr3], dtype=np.complex128)

    return rhotot_r.real, rhodiff_r.real


def read_wavefunction_file_hdf5(filename):
    """
    Reads an hdf5 wavefunction file written with QE. Returns a dictionary with
    the data structure in the hdf5 file. 
    """

    f = h5py.File(filename, "r")
    nkpoints = len(f["KPOINT1"].attrs.values())
    #print ("nkpoints = ",nkpoints)

    wavefunctions = {}

    for i in range(0,nkpoints):
        temp = {}
        kpoint_label = "KPOINT"+str(i+1)
        # read the attributes at each kpoint
        attrs_to_read = ["gamma_only", "igwx", "ik", "ispin","ngw","nk","nbnd","nspin","scale_factor"]
        for attr in attrs_to_read:
            temp[attr] = f[kpoint_label].attrs.get(attr)
        for iband in range(0,temp["nbnd"]):
            band_label = "BAND"+str(iband+1)
            temp[band_label] = np.array(f[kpoint_label][band_label])
        
        wavefunctions[kpoint_label] = temp
        
    return wavefunctions
    
    
################################################################################
# Reader of pseudopotential files and auxiliary functions.
################################################################################
# Warning: limited functionalities for now
#
def get_tag(line):
    """
    Check if the input string is an xml tag, i.e. it contains between "<" and ">" the "/" and any alphanumeric character.
    If so, returns the string between  "<" and ">". If "/" is present, it is in [0] position in the returned string.
    If not a tag, returns None
    """

    import re

    line = line.strip(" \n\t")         # first strip spaces, endline chars, tabs
    pat = re.compile(r'<\/?[\w\ =\+\-\.\"]+\/?>')    # a tag may contain between "<" and ">" the "/" and any alphanumeric character
    if pat.match(line):
        return line.strip(" <>")     # returns the tag without "<" and ">"


def read_pseudo_file(filename):

    """
    This function reads a pseudopotential file in the QE UPF format (text), returning
        the content of each tag in a dictionary. 
    WARNING: does not handle multiple tags with the same name yet and has limited 
    functionalities for now. It is meant to be used only for postqe, not as a general
    reader of pseudopotentials files.
    """

    pseudo = {}

    with open (filename, 'r') as temp:
        pslines = [ line.replace('&input','&amp;input') for line in temp ]
    try:
        psroot = ET.fromstringlist(pslines)
    except ET.ParseError:
        return pseudo

    # PP_INFO
    pp_info = psroot.find('./PP_INFO').text
    try:
        pp_input = psroot.find('./PP_INFO/PP_INPUTFILE').text
    except:
        pp_input = ""
    pseudo.update(dict(PP_INFO=dict(INFO=pp_info, PP_INPUT=pp_input)))

    #PP_HEADER
    pp_header = dict(psroot.find('./PP_HEADER').items())
    pseudo.update(dict(PP_HEADER=pp_header))
    #PP_MESH
    pp_mesh = dict(psroot.find('./PP_MESH').items())
    pp_r   = np.array([float(x) for x in psroot.find('./PP_MESH/PP_R').text.split()])
    pp_rab = np.array([float(x) for x in psroot.find('./PP_MESH/PP_RAB').text.split()])
    pp_mesh.update(dict(PP_R=pp_r, PP_RAB = pp_rab))
    pseudo.update(dict(PP_MESH = pp_mesh))
    #PP_LOCAL
    pp_local = None
    node = psroot.find('./PP_LOCAL')
    if not node is None:
        pp_local = np.array([x for x in map(float, node.text.split() )])

    pseudo.update(dict(PP_LOCAL = pp_local))
    #
    node = psroot.find('./PP_RHOATOM')
    if not node is None:
        pp_rhoatom = np.array([v for v in map(float,node.text.split()) ])
    else:
        pp_rhoatom = None

    pseudo.update(dict(PP_RHOATOM=pp_rhoatom))
    #
    node = psroot.find('./PP_NONLOCAL')
    if not node is None:
        betas = list()
        dij = None
        pp_aug = None
        pp_q = None
        for el in node:
            if 'PP_BETA' in el.tag:
                beta = dict( el.items() )
                val  = np.array([x for x in map(float,el.text.split() )])
                beta.update(dict(beta = val))
                betas.append(beta)
            elif 'PP_DIJ' in el.tag:
                dij = np.array([ x for x in map(float,el.text.split() )])
            elif 'PP_AUGMENTATION' in el.tag:
                pp_aug = dict(el.items () )
                pp_qijl = list()
                pp_qij  = list()
                for q in el:
                    if 'PP_QIJL' in q.tag:
                        qijl = dict( q.items() )
                        val = np.array( [ x for x in map(float, q.text.split() )])
                        qijl.update(dict(qijl = val))
                        pp_qijl.append(qijl)
                    elif 'PP_QIJ' in q.tag:
                        qij = dict(q.items() )
                        val = np.array( [x for x in map(float,q.text.split() )])
                        qij.update(dict(qij = val))
                        pp_qij.append(qij)
                    elif q.tag =='PP_Q':
                        pp_q = np.array( [x for x in map(float, q.text.split() )])
                pp_aug.update(dict(PP_QIJL=pp_qijl, PP_QIJ = pp_qij, PP_Q = pp_q) )
        pp_nonlocal = dict(PP_BETA = betas, PP_DIJ = dij, PP_AUGMENTATION = pp_aug )
    else:
        pp_nonlocal = None
    pseudo.update(dict(PP_NONLOCAL = pp_nonlocal))

    return pseudo


def write_charge(filename, charge, header):
    """
    Write the charge or another quantity calculated by postqe into a text file *filename*.
    """
    
    fout = open(filename, "w")
    
    # The header contains some information on the system, the grid nr, etc.
    fout.write(header)
    nr = charge.shape
    count = 0
    # Loop with the order as in QE files
    for z in range(0,nr[2]):
        for y in range(0,nr[1]):
            for x in range(0,nr[0]):
                fout.write("  {:.9E}".format(charge[x,y,z]))
                count += 1
                if (count%5==0):
                    fout.write("\n")
                        
    fout.close()
    
    
def create_header(prefix, nr, nr_smooth, ibrav, celldms, nat, ntyp, atomic_species, atomic_positions):
    """
    Creates the header lines for the output charge (or potential) text file and is called by *write_charge*.
    The format is:

    system_prefix
    fft_grid (nr1,nr2,nr3)  fft_smooth (nr1,nr2,nr3)  nat  ntyp
    ibrav     celldms (6 real as in QE)
    missing line with respect to pp.x
    List of atoms
    List of positions for each atom

    """

    text = "# "+prefix+"\n"
    text += "# {:8d} {:8d} {:8d} {:8d} {:8d} {:8d} {:8d} {:8d}\n".format(nr[0],nr[1],nr[2],nr_smooth[0],nr_smooth[1],nr_smooth[2],nat,ntyp)
    text += "# {:6d}    {:8E}  {:8E}  {:8E}  {:8E}  {:8E}  {:8E}\n".format(ibrav,*celldms)
    # TODO This line is to be implemented
    text += "#      "+4*"XXXX   "+"\n"
    
    ityp = 1
    for typ in atomic_species:
        text += "# {:4d} ".format(ityp)+typ["@name"]+"\n"
        ityp += 1

    ipos = 1
    for pos in atomic_positions:
        text += "# {:4d}  ".format(ipos)
        coords = [float(x) for x in pos['$'] ]
        text += " {:9E} {:9E} {:9E}  ".format(*coords)
        text += pos["@name"]+"\n"
        ipos += 1
    
    return text
    
 
def read_postqe_output_file(filename):
    """
    This function reads the output charge (or other quantity) as the output 
    format of postqe. 
    """
    
    tempcharge = []
    count = 0
    nr = np.zeros(3,dtype=int)
    with open(filename, "r") as lines:
        for line in lines:
            linesplit=line.split()
            if count==1:
                nr[0] = int(linesplit[1])
                nr[1] = int(linesplit[2])
                nr[2] = int(linesplit[3])
            if linesplit[0]!='#':                       # skip the first lines beginning with #
                for j in range(0,len(linesplit)):       # len(linesplit)=5 except maybe for the last line
                    tempcharge.append(float(linesplit[j]))
            count += 1

    charge = np.zeros((nr[0],nr[1],nr[2]))
    count = 0
    # Loops according to the order it is done in QE
    for z in range(0,nr[2]):
        for y in range(0,nr[1]):
            for x in range(0,nr[0]):
                charge[x,y,z] = tempcharge[count]
                count += 1

    return charge


def read_EtotV(fname):
    """
    Read cell volumes and the corresponding energies from input file *fname*
    (1st col, volumes, 2nd col energies). Units must be :math:`a.u.^3` and
    :math:`Ryd/cell`
    """
    Vx = []
    Ex = []

    with open(fname, "r") as lines:
        for line in lines:
            linesplit = line.split()
            V = float(linesplit[0])
            E = float(linesplit[1])
            Vx.append(V)
            Ex.append(E)

    return np.array(Vx), np.array(Ex)
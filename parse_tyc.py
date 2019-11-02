"""Routines for parsing the TYC2 data."""

import gzip
import os
import tarfile

import numpy as np
import astropy.units as u

from astropy import io
from astropy.table import join, unique, vstack

def load_gaia_tyc():
    """Load the Gaia DR2 TYC2 sources."""
    print('Loading Gaia DR2 sources for TYC2')
    col_names = ['source_id', 'tyc2_id', 'ra', 'dec', 'phot_g_mean_mag', 'bp_rp',
                 'teff_val', 'r_est']
    gaia = io.ascii.read(os.path.join('gaia', 'gaiadr2_tyc-result.csv'),
                         include_names=col_names,
                         format='csv')

    tycs = np.array(np.char.split(gaia['tyc2_id'], '-').tolist()).astype(np.int64)
    gaia['TYC'] = tycs[:, 0] + tycs[:, 1]*10000 + tycs[:, 2]*1000000000
    gaia.remove_column('tyc2_id')

    gaia['ra'].unit = u.deg
    gaia['dec'].unit = u.deg
    gaia['phot_g_mean_mag'].unit = u.mag
    gaia['bp_rp'].unit = u.mag
    gaia['teff_val'].unit = u.K
    gaia['r_est'].unit = u.pc

    return gaia

def load_tyc_spec():
    """Load the TYC2 spectral type catalogue."""
    print('Loading TYC2 spectral types')
    with tarfile.open(os.path.join('vizier', 'tyc2spec.tar.gz')) as tf:
        with tf.extractfile('./ReadMe') as readme:
            col_names = ['TYC1', 'TYC2', 'TYC3', 'SpType']
            reader = io.ascii.get_reader(io.ascii.Cds,
                                         readme=readme,
                                         include_names=col_names)
            reader.data.table_name = 'catalog.dat'
            with tf.extractfile('./catalog.dat.gz') as gzf, gzip.open(gzf, 'rb') as f:
                data = reader.read(f)

    data['TYC'] = data['TYC1'] + data['TYC2']*10000 + data['TYC3']*1000000000
    data.remove_columns(['TYC1', 'TYC2', 'TYC3'])
    return data

def load_ascc():
    """Load ASCC from VizieR archive."""
    def load_section(tf, info):
        with tf.extractfile('./ReadMe') as readme:
            col_names = ['Bmag', 'Vmag', 'e_Bmag', 'e_Vmag', 'd3', 'TYC1', 'TYC2', 'TYC3', 'HD',
                         'Jmag', 'e_Jmag', 'Hmag', 'e_Hmag', 'Kmag', 'e_Kmag']
            reader = io.ascii.get_reader(io.ascii.Cds,
                                         readme=readme,
                                         include_names=col_names)
            reader.data.table_name = 'cc*.dat'
            print('  Loading ' + os.path.basename(info.name))
            with tf.extractfile(info) as gzf, gzip.open(gzf, 'rb') as f:
                section = reader.read(f)

        section = section[section['TYC1'] != 0]

        section['TYC'] = section['TYC1'] + section['TYC2']*10000 + section['TYC3']*1000000000
        section.remove_columns(['TYC1', 'TYC2', 'TYC3'])

        convert_cols = ['Bmag', 'Vmag', 'e_Bmag', 'e_Vmag', 'Jmag', 'e_Jmag', 'Hmag', 'e_Hmag',
                        'Kmag', 'e_Kmag']
        for col in convert_cols:
            section[col] = section[col].astype(np.float64)
            section[col].convert_unit_to(u.mag)
            section[col].format = '.3f'

        return section

    def is_data(info):
        sections = os.path.split(info.name)
        return (len(sections) == 2 and
                sections[0] == '.' and
                sections[1].startswith('cc'))

    print('Loading ASCC')
    with tarfile.open(os.path.join('vizier', 'ascc.tar.gz'), 'r:gz') as tf:
        combined = vstack([load_section(tf, m) for m in tf if is_data(m)],
                          join_type='exact')

    data = unique(combined.group_by(['TYC', 'd3']), keys=['TYC'])
    data.remove_column('d3')
    return data

def merge_tables():
    """Merges the tables."""
    data = join(load_gaia_tyc(), load_tyc_spec(), keys=['TYC'], join_type='left')
    data = join(data, load_ascc(), keys=['TYC'], join_type='left')
    data['HD'].mask = np.logical_or(data['HD'].mask, data['HD'] == 0)
    return data

def process_tyc():
    """Processes the TYC data."""
    data = merge_tables()
    data.rename_column('r_est', 'dist_use')
    return data

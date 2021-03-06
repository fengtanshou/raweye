import sys
import argparse
import numpy as np
from colour_demosaicing import demosaicing_CFA_Bayer_bilinear as demosaicing
from colour_hdri import (
        EXAMPLES_RESOURCES_DIRECTORY,
        tonemapping_operator_simple,
        tonemapping_operator_normalisation,
        tonemapping_operator_gamma,
        tonemapping_operator_logarithmic,
        tonemapping_operator_exponential,
        tonemapping_operator_logarithmic_mapping,
        tonemapping_operator_exponentiation_mapping,
        tonemapping_operator_Schlick1994,
        tonemapping_operator_Tumblin1999,
        tonemapping_operator_Reinhard2004,
        tonemapping_operator_filmic)
import matplotlib.pyplot as plt
#from matplotlib.image import imsave
from scipy.misc import imsave

g_ccm = np.array([[1.2085, -0.2502, 0.0417],
                  [-0.1174, 1.1625, -0.0452],
                  [0.0226, -0.2524, 1.2298]])

#@profile
def rawfAwb(rawf, rgain, bgain, bayer='rggb'):
    hrb_map = {'rggb': np.array([[rgain, 1.0],[1.0, bgain]]),
               'bggr': np.array([[bgain, 1.0],[1.0, rgain]]),
               'grbg': np.array([[1.0, rgain],[bgain, 1.0]]),
               'gbrg': np.array([[1.0, bgain],[rgain, 1.0]])}

    h_rb = hrb_map[bayer]
    b_width = rawf.shape[1]
    rawf = np.hsplit(rawf, b_width/2)
    rawf = np.vstack(rawf)
    b_shape = rawf.shape
    rawf = rawf.reshape(-1,2,2)

    rawf = rawf * h_rb

    rawf = rawf.reshape(b_shape)
    rawf = np.hstack(np.vsplit(rawf, b_width/2))
    return rawf

#@profile
def mipirawtorawf(raw, h):
    raw10 = raw.reshape(h, -1, 5).astype(np.uint16) 
    a,b,c,d,e = [raw10[...,x] for x in range(5)]
    x1 = (a << 2) + ((e >> 0) & 0x03)
    x2 = (b << 2) + ((e >> 2) & 0x03)
    x3 = (c << 2) + ((e >> 4) & 0x03)
    x4 = (d << 2) + ((e >> 6) & 0x03)
    x1 = x1.reshape(h, -1, 1)
    x2 = x2.reshape(h, -1, 1)
    x3 = x3.reshape(h, -1, 1)
    x4 = x4.reshape(h, -1, 1)
    x = np.dstack((x1, x2, x3, x4))
    x = x.reshape(h, -1)
    return x / np.float(2**10)

#@profile
def raw10torawf(raw, h):
    raw10 = raw.reshape(h, -1, 5).astype(np.uint16) 
    a,b,c,d,e = [raw10[...,x] for x in range(5)]
    x1 = a + ((b & 0x03) << 8)
    x2 = (b >> 2) + ((c & 0x0f) << 6)
    x3 = (c >> 4) + ((d & 0x3f) << 4)
    x4 = (d >> 6) + (e << 2)
    x1 = x1.reshape(h, -1, 1)
    x2 = x2.reshape(h, -1, 1)
    x3 = x3.reshape(h, -1, 1)
    x4 = x4.reshape(h, -1, 1)
    x = np.dstack((x1, x2, x3, x4))
    x = x.reshape(h, -1)
    return x / np.float(2**10)

#@profile
def raw16torawf(raw, h):
    return raw.reshape((h, -1))/np.float(2**16)

if "__main__" == __name__:
    parser = argparse.ArgumentParser(description='Show raw image or convert it to jpeg/png.')
    parser.add_argument('-H', dest='height', type=int, required=True)
    parser.add_argument('-W', dest='width', type=int)
    parser.add_argument('-s', dest='offset', type=int, default = 0)
    parser.add_argument('-t', dest='rawtype', choices = ['raw10', 'raw16', 'raw'],
                        help='raw10: continue 10bits, raw: mipi 10bits, raw16: 16bits')
    parser.add_argument('-b', dest='bayer', choices=['rggb', 'bggr', 'grbg', 'gbrg', 'y'], default='rggb')
    parser.add_argument('-d', dest='dgain', type=float, default=1.0, help='digit gain apply')
    parser.add_argument('-o', dest='outfile', metavar='FILE', help='write image to FILE')
    parser.add_argument('infile', metavar='InputRawFile', help='source raw image')
    args = parser.parse_args()

    if args.rawtype == None:
        args.rawtype = args.infile.split('.')[1]

    print(args.rawtype, args.bayer, args.height, args.dgain, args.infile, args.outfile)

    rawmap = {'raw10': (np.uint8,  raw10torawf),
              'raw'  : (np.uint8,  mipirawtorawf),
              'pgm'  : (np.uint16, raw16torawf),
              'raw16': (np.uint16, raw16torawf)}

    if args.rawtype not in rawmap:
        print('unknown raw type:', args.rawtype)
        sys.exit(0)

    dataType, rawtorawf = rawmap[args.rawtype]

    with open(args.infile, 'rb') as infile:
        infile.read(args.offset)
        raw = np.fromfile(infile, dataType)

    if args.width is not None and args.rawtype == 'raw10':
        raw.resize((int(args.width * 1.25 * args.height)))

    if args.bayer != 'y':
        #raw = raw - 16
        #raw = (raw > 0) * raw

        rawf = rawtorawf(raw, args.height)
        print('raw image shape:', rawf.shape)

        rawf = rawfAwb(rawf, 1.8, 1.8, args.bayer)

        rgb = demosaicing(rawf, args.bayer)
    else:
        raw = raw / np.float(2**16)
        rgb = raw.reshape(args.height, -1)

    if args.dgain > 1.0:
        rgb = rgb * args.dgain

    #rgb = np.dot(rgb, g_ccm)

    #rgb = rgb / (rgb + 1)
    #rgb = tonemapping_operator_simple(rgb)

    np.clip(rgb, 0.0, 1.0, out=rgb)

    if args.outfile:
        imsave(args.outfile, rgb)
    else:
        #plt.subplot(1, 3, 1)
        cmap=None
        if args.bayer == 'y':
            cmap = 'gray'
        plt.imshow(rgb, cmap=cmap)
        plt.show()

import os, argparse
from io_util import *
from texture_asset import BYTE_PER_PIXEL

DDS_FORMAT = {
    'DXT1/BC1': ['DXT1', 71, 72],     #DXGI_FORMAT_BC1_TYPELESS
    'DXT5/BC3': ['DXT5', 77, 78],     #DXGI_FORMAT_BC3_TYPELESS	
    'BC4/ATI1': [80, 'ATI1', 'BC4U'], #DXGI_FORMAT_BC4_UNORM
    'BC5/ATI2': [83, 'ATI2', 'BC5U'], #DXGI_FORMAT_BC5_UNORM
    'BC6H(unsigned)': [95],           #DXGI_FORMAT_BC6H_UF16
    'BC6H(signed)': [96],             #DXGI_FORMAT_BC6H_SF16
    'BC7': [98, 99],                  #DXGI_FORMAT_BC7_TYPELESS
    'FloatRGBA': [10],                #DXGI_FORMAT_R16G16B16A16_FLOAT
    'B8G8R8A8(sRGB)': [91]            #DXGI_FORMAT_B8G8R8A8_UNORM_SRGB
}

def get_dds_format(form):
    for k in DDS_FORMAT:
        if form in DDS_FORMAT[k]:
            return k
    raise RuntimeError('Unsupported DDS format. ({})'.format(form))

class DDSHeader:
    MAGIC = b'\x44\x44\x53\x20'

    def __init__(self, width, height, mipmap_num, format_name):
        self.width = width
        self.height = height
        self.mipmap_num = mipmap_num
        self.format_name = format_name
        self.byte_per_pixel = BYTE_PER_PIXEL[self.format_name]

    #read header
    def read(f):
        head = f.read(4)             #Magic=='DDS '
        check(head, DDSHeader.MAGIC)
        read_const_uint32(f, 124)    #Size==124
        f.seek(4,1)                  #Flags
        height = read_uint32(f)      #Height
        width = read_uint32(f)       #Width
        f.seek(8,1)                  #PitchOrLinearSize, Depth
        mipmap_num = read_uint32(f)  #MipMapCount
        mipmap_num += mipmap_num==0
        f.seek(44, 1)                #Reserved1[11]
        read_const_uint32(f, 32)     #PfSize==32
        read_const_uint32(f, 4)      #PfFlags==4
        fourCC=f.read(4).decode()    #FourCC
        f.seek(40, 1)                #BitCount, BitMask
                                     #Caps, Caps2, ReservedCaps[2], Reserved2
        
        #DXT10 header
        if fourCC=='DX10':
            dxgi_format=read_uint32(f)      #dxgiFormat
            l = read_uint32_array(f, len=3) #resourceDimension==3
            check(l, [3,0,1])               #miscFlag==0
                                            #arraySize==1
            f.seek(4, 1)                    #miscFlag2
        else:
            dxgi_format=fourCC
        
        format_name = get_dds_format(dxgi_format)
        return DDSHeader(width, height, mipmap_num, format_name)

    #write header
    def write(f, header):
        mipmap_num=header.mipmap_num
        dxgi_format = DDS_FORMAT[header.format_name][0]
        if type(dxgi_format)==type(''):
            fourCC=dxgi_format
        else:
            fourCC='DX10'

        f.write(DDSHeader.MAGIC)
        write_uint32(f, 124) #Size==124

        #flags
        write_uint8(f, 7)
        write_uint8(f, 16)
        write_uint8(f, 8+2*(mipmap_num>1))
        write_uint8(f, 0)

        write_uint32(f, header.height)
        write_uint32(f, header.width)

        #PitchOrLinearSize
        write_uint32(f, int(header.width*header.height*header.byte_per_pixel))

        write_uint32(f, 1) #Depth
        write_uint32(f, mipmap_num)

        #Reserved1[11]
        write_null_array(f, 9)
        f.write('FF7R'.encode())
        write_null(f)

        write_uint32(f, 32) #PfSize==32
        write_uint32(f, 4) #PfFlags
        f.write(fourCC.encode()) #fourCC
        write_null_array(f, 5) #BitCount, BitMask

        #caps
        write_uint8(f, (mipmap_num>1)*8)
        write_uint8(f, 16)
        write_uint8(f, (mipmap_num>1)*64)
        write_uint8(f, 0)

        write_null_array(f ,4) #caps2, reservedCaps, reserved2

        #write dxt10 header
        if fourCC=='DX10':
            write_uint32(f, dxgi_format)
            write_uint32_array(f, [3,0,1])
            write_uint32(f, 0)

    def print(self):
        print('  height: {}'.format(self.height))
        print('  width: {}'.format(self.width))
        print('  mipmap num: {}'.format(self.mipmap_num))
        print('  format: {}'.format(self.format_name))
        print('  byte per pixel: {}'.format(self.byte_per_pixel))

class DDS:
    def __init__(self, header, mipmap_data, mipmap_size):
        self.header = header
        self.mipmap_data = mipmap_data
        self.mipmap_size = mipmap_size

    #load dds file
    def load(file, verbose=False):
        if file[-3:]!='dds':
            raise RuntimeError('Not DDS.')
        print('load: ' + file)
        with open(file, 'rb') as f:
            #read header
            header = DDSHeader.read(f)

            mipmap_num = header.mipmap_num
            byte_per_pixel = header.byte_per_pixel
            height = header.height
            width = header.width
            mipmap_data = []
            mipmap_size = []

            #read mipmaps
            for i in range(mipmap_num):

                #mipmap sizes are multiples of 4
                if height%4!=0:
                    height+=4-height%4
                if width%4!=0:
                    width+=4-width%4
                
                #read mipmap data
                size = height*width*byte_per_pixel
                if size!=int(size):
                    raise RuntimeError('The size of mipmap data is not int. This is unexpected.')
                data = f.read(int(size))
                
                #print mipmap info
                if verbose:
                    print('  Mipmap {}'.format(i))
                    print('    size (w, h): ({}, {})'.format(width, height))

                #store mipmap data
                mipmap_data.append(data)
                mipmap_size.append([int(width), int(height)])
                height = height//2
                width = width//2

            header.print()
            check(f.tell(), get_size(f), msg='Parse Failed. This is unexpected.')

        return DDS(header, mipmap_data, mipmap_size)
            
    #texture asset to dds
    def asset_to_DDS(asset):
        #make dds header
        header = DDSHeader(0, 0, 0, asset.format_name)

        mipmap_data=[]
        mipmap_size=[]

        #get ubulk mipmaps
        if asset.has_ubulk:
            for d, meta in zip(asset.ubulk_map_data, asset.ubulk_map_meta):
                mipmap_data.append(d)
                mipmap_size.append([meta.width, meta.height])

        #get uexp mipmaps
        for d, meta in zip(asset.uexp_map_data, asset.uexp_map_meta):
            mipmap_data.append(d)
            mipmap_size.append([meta.width, meta.height])

        #update header
        header.width, header.height = asset.get_max_size()
        header.mipmap_num=len(mipmap_data)

        return DDS(header, mipmap_data, mipmap_size)

    #save as dds
    def save(self, file):
        with open(file, 'wb') as f:
            #write header
            DDSHeader.write(f, self.header)

            #write mipmap data
            for d in self.mipmap_data:
                f.write(d)

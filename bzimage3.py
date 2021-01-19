#!/usr/bin/env python
# coding: utf-8

# #keyence in single field zstack multicolor capture mode 
# #yields an overlay and 4 single channel tif files (CH1,CH2,CH3,CH4 AS BGRW)
# #for each z position 
# #example:
# #B-DAPI G-PCAD R-RFP W-A6_20X (good exposure)_Z001_CH1.tif
# #B-DAPI G-PCAD R-RFP W-A6_20X (good exposure)_Z001_CH2.tif
# #B-DAPI G-PCAD R-RFP W-A6_20X (good exposure)_Z001_CH3.tif
# #B-DAPI G-PCAD R-RFP W-A6_20X (good exposure)_Z001_CH4.tif
# #B-DAPI G-PCAD R-RFP W-A6_20X (good exposure)_Z001_Overlay.tif
# 
# #problem is the 4th color is white which contaminates other channels
# #only psuedocolors used should be RGB
# #this script should take a folder with these images and 
# # (1) make 3 color overlays (excluding one color)
# # (2) stack the 3 color overlays and save as tif

import os
import re
import numpy as np
import pprint
from multiprocessing import Process, Pool, freeze_support
import cv2
import time
import zipfile
import time
import tifffile
import imagecodecs
import sys



def mip(worklist): #Maximum Intensity Projection
    r_layers = []
    g_layers = []
    b_layers = []
    w_layers = []
    for item in worklist:
        r = cv2.imread(item[0])
        g = cv2.imread(item[1])
        b = cv2.imread(item[2])
        w = cv2.imread(item[3])
        try:
            if np.average(r[:,:,0])>0: #if R multilayered since keyence saves even single chann as RGB 3 layer
                r = r[:,:,0]
            elif np.average(r[:,:,1])>0:
                r = r[:,:,1]
            elif np.average(r[:,:,2])>0:
                r = r[:,:,2]
            else:
                r = r[:,:,0] #in case all channels are pure black
        except:
            r = r[:,:]

        try:
            if np.average(g[:,:,0])>0: #if G multilayered
                g = g[:,:,0]
            elif np.average(g[:,:,1])>0:
                g = g[:,:,1]
            elif np.average(g[:,:,2])>0:
                g = g[:,:,2]
            else:
                g = g[:,:,0]
        except:
            g = g[:,:]

        try:
            if np.average(b[:,:,0])>0: #if B multilayered
                b = b[:,:,0]
            elif np.average(b[:,:,1])>0:
                b = b[:,:,1]
            elif np.average(b[:,:,2])>0:
                b = b[:,:,2]
            else:
                b = b[:,:,0]
        except:
            b = b[:,:]

        try:
            if np.average(w[:,:,0])>0: #if W multilayered
                w = w[:,:,0]
            elif np.average(w[:,:,1])>0:
                w = w[:,:,1]
            elif np.average(w[:,:,2])>0:
                w = w[:,:,2]
            else:
                w = w[:,:,0]
        except:
            w = w[:,:]

        r_layers.append(r)
        g_layers.append(g)
        b_layers.append(b)
        w_layers.append(w)
        r_mip = np.max(r_layers,axis=0) #max intensity projection
        g_mip = np.max(g_layers,axis=0) #max intensity projection
        b_mip = np.max(b_layers,axis=0) #max intensity projection
        w_mip = np.max(w_layers,axis=0) #max intensity projection
    return [r_mip,g_mip,b_mip,w_mip]

def allocator(worklist): #chunks the worklist for a given tile into blocks of 30 four color zlevels
    blocklist = []
    processing_blocks = []
    if len(worklist) < 30:
        blocklist.append((0,len(worklist)))

    else:
        block = len(worklist)
        for block in range(block//30):
            start = block*30
            end = start+30
            blocklist.append((start,end))
    if blocklist[-1][1] != len(worklist):
        blocklist.append((blocklist[-1][1],len(worklist))) #append the remainder block if there is one
    pp.pprint('processing block... # blocks per tile: ' + str(len(blocklist))+' (30 images max per block)')

    for zrange in blocklist:
    #pp.pprint(worklist[zrange[0]:zrange[1]])
        processing_blocks.append(worklist[zrange[0]:zrange[1]])

    return list(zip(blocklist,processing_blocks))

def blocksize(worklist): #for progress calculation displays
    blocklist = []
    if len(worklist) < 30:
        blocklist.append((0,len(worklist)))
    else:
        block = len(worklist)
        for block in range(block//30):
            start = block*30
            end = start+30
            blocklist.append((start,end))
    if blocklist[-1][1] != len(worklist):
        blocklist.append((blocklist[-1][1],len(worklist))) #append the remainder block if there is one
    return int(len(blocklist))

def getworklist(tile):
    worklist = []
    try:
        for z in unique_z_pos:
            r = proc_folder+base_name+tile+'_'+z+'_'+channels['R']+'.tif'
            g = proc_folder+base_name+tile+'_'+z+'_'+channels['G']+'.tif'
            b = proc_folder+base_name+tile+'_'+z+'_'+channels['B']+'.tif'
            w = proc_folder+base_name+tile+'_'+z+'_'+channels['W']+'.tif'
            worklist.append([r,g,b,w])
        return worklist
    except:
        print("oh god it isn't a stitched image")
        for z in unique_z_pos:
            r = proc_folder+base_name+z+'_'+channels['R']+'.tif'
            g = proc_folder+base_name+z+'_'+channels['G']+'.tif'
            b = proc_folder+base_name+z+'_'+channels['B']+'.tif'
            w = proc_folder+base_name+z+'_'+channels['W']+'.tif'
            worklist.append([r,g,b,w])
        return worklist


def col_fusion(img_list,rows,cols,overlap):
    print('**********\nstarting column fusion\n**********')
    print('grid dimensions are %d rows by %d columns\n' %  (rows,cols))

    column_fusions = []
    if cols > 1:

        rows = rows

        ims = sorted(img_list)
        mylist = [x for x in range(0,len(img_list))]
        advance_one = mylist[1:]

        cols = cols
        all_rows = mylist[::cols]
        left_right_rows = mylist[::cols*2]
        right_left_rows = sorted(list(set(all_rows)-set(left_right_rows)))

        print('column fusion: L-R rows are %s' % str(left_right_rows))
        print('column fusion: R-L rows are %s' % str(right_left_rows))


        ###fuse left to right rows overlapping inside tile edges###
        for row in left_right_rows:
            foo1 = []
            i=0
            for tile in [x for x in range(0,cols)]:
                if i < cols:
                    fusion_img = cv2.imread(ims[row+i])
                    col_dims = fusion_img.shape[1]
                    col_margin = int(col_dims * overlap//2)
                    #print(margin)
                    if i == 0: #left edge tile
                        foo1.append(fusion_img[:,0:-col_margin])
                        i+=1
                        print('column fusion: L-R left')
                    elif i == cols-1: #right edge tile
                        foo1.append(fusion_img[:,col_margin:col_dims])
                        i+=1
                        print('column fusion: L-R right')
                    else:
                        foo1.append(fusion_img[:,col_margin:-col_margin]) #middle tiles
                        i+=1
                        print('column fusion: L-R mid')
            print('running column fusion: L-R rows')
            print([x.shape for x in foo1])
            foobar1 = cv2.hconcat([x for x in foo1])

            column_fusions.append((row,foobar1))



            ###fuse right to left rows###
        for row in right_left_rows:
            foo2 = []
            i=0
            for tile in [x for x in range(0,cols)]:
                if i < cols:
                    fusion_img = cv2.imread(ims[row+i])
                    col_dims = fusion_img.shape[1]
                    col_margin = int(col_dims * overlap//2)
                    #print(margin)
                    if i == 0: #RIGHT edge tile (OPPOSITE FROM ABOVE)
                        foo2.append(fusion_img[:,col_margin:col_dims])
                        i+=1
                        print('column fusion: R-L right')
                    elif i == cols-1: #LEFT edge tile
                        foo2.append(fusion_img[:,0:-col_margin])
                        i+=1
                        print('column fusion: R-L left')
                    else:
                        foo2.append(fusion_img[:,col_margin:-col_margin]) #middle tiles
                        i+=1
                        print('column fusion: R-L mid')
            print('running column fusion: R-L rows')
            print([x.shape for x in foo2])
            foobar2 = cv2.hconcat([x for x in foo2][::-1]) #reverse the list so it fuses right since the tiles snaked back

            column_fusions.append((row,foobar2))
            column_fusions = sorted(column_fusions)

            print('column fusion has %d/%d items' % (len(column_fusions),rows))
    else:
        #return the images from the single column
        ims = sorted(img_list)
        i = 0
        for image in ims:
            image = cv2.imread(image)
            column_fusions.append((i,image))
            i+=1
        print("FIX")
    return column_fusions

def row_fusion(fused_cols,rows,cols,overlap):
    print('\n**********\nstarting row fusion\n**********')
    print('grid dimensions are %d rows by %d columns\n' %  (rows,cols))
    row_fusions = []
    column_fusions=sorted(fused_cols)
    if rows > 1:
        j=0
        for cf in [x for x in range(0,rows)]:
            print('cf is %d' % cf)
            fusion_img = column_fusions[cf][1]
            #print('fusion img shape is ' +str(fusion_img.shape))
            row_dims = fusion_img.shape[0]
            row_margin = int(row_dims * overlap//2)

            #print(margin)
            if j == 0: #TOP FUSED ROW
                row_fusions.append(fusion_img[0:-row_margin,:])

                j+=1
                print('row fusion: top')
            elif j == rows-1: #BOTTOM FUSED ROW
                row_fusions.append(fusion_img[row_margin:row_dims,:])
                j+=1
                print('row fusion: bottom')
            else:
                row_fusions.append(fusion_img[row_margin:-row_margin,:]) #MIDDLE FUSED ROW(S)
                j+=1
                print('row fusion: mid')

        print('row fusion has %d/%d items' % (len(row_fusions),rows))
        print('running row fusion')
        final_fusion = cv2.vconcat(row_fusions) #fuse the rows
    else:
        final_fusion = column_fusions[0][1] #WHAT IF THERE IS ONLY 1 ROW AND NOTHING TO FUSE?
    return final_fusion









#find all the tile positions. keyence tiles in a snaking pattern left to right then down and right to left, etc and the overlap is ~30% in both x and y
#1 2 3
#6 5 4
#7 8 9
def find_tiles(fins):
    try:
        tile_re = re.compile(r'\d\d\d\d\d')
        tiles = []
        for file in fins:
            tiles.append(re.search(tile_re,file).group(0))
        tiles = np.unique(tiles).tolist()
        return tiles
    except:
        print("oh god it isn't a stitched image")
        return None






def main(tiles,unique_zs):
    #putting it all together- the run script

    if tiles != None:
        k = 1 #part of blocks progress counter
        for tile in tiles:
            worklist = [] #list of tiles, and tiles contain all z stacks of all 4 color channels
            worklist.append(getworklist(tile))
            worklist = worklist[0] #de-nestifying
            current_block = k * 4 * len(np.unique(unique_zs))
            print('tile %s: worklist completion is %d/%d items' % (tile,current_block,len(worklist)))
            k += 1
            #process the blocks with multiprocessing (pool and map)
            with Pool() as po:
                res = po.map_async(mip, ((i,) for i in allocator(worklist)[0][1]))
                fetch = res.get()

            r_layers = []
            g_layers = []
            b_layers = []
            w_layers = []
            for chunked_intermediate in fetch:
                r = chunked_intermediate[0]
                g = chunked_intermediate[1]
                b = chunked_intermediate[2]
                w = chunked_intermediate[3]
                r_layers.append(r)
                g_layers.append(g)
                b_layers.append(b)
                w_layers.append(w)
            mip_r = np.max(r_layers,axis=0)
            mip_g = np.max(g_layers,axis=0)
            mip_b = np.max(b_layers,axis=0)
            mip_w = np.max(w_layers,axis=0)

            rgb = np.dstack([mip_r,mip_g,mip_b])

            cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+tile+'_RGB.tif',rgb[...,::-1]) #can't stitch multicolor images
            #cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+tile+'_R.tif',mip_r)
            #cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+tile+'_G.tif',mip_g)
            #cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+tile+'_B.tif',mip_b)
            cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+tile+'_W.tif',mip_w)
        print("tiled image job done")

    else:
        print("going to single image workflow")

        worklist = getworklist(tifs_no_overlays)
            #worklist.append(getworklist(tifs_no_overlays))
            #worklist = worklist[0] #de-nestifying


            #process the blocks with multiprocessing (pool and map)
        with Pool() as po:
            res = po.map_async(mip, ((i,) for i in allocator(worklist)[0][1]))
            fetch = res.get()



        r_layers = []
        g_layers = []
        b_layers = []
        w_layers = []
        for chunked_intermediate in fetch:
            r = chunked_intermediate[0]
            g = chunked_intermediate[1]
            b = chunked_intermediate[2]
            w = chunked_intermediate[3]
            r_layers.append(r)
            g_layers.append(g)
            b_layers.append(b)
            w_layers.append(w)
        mip_r = np.max(r_layers,axis=0)
        mip_g = np.max(g_layers,axis=0)
        mip_b = np.max(b_layers,axis=0)
        mip_w = np.max(w_layers,axis=0)

        rgb = np.dstack([mip_r,mip_g,mip_b])


        cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+'_RGB.tif',rgb[...,::-1]) #can't stitch multicolor images
            #io.imsave(proc_folder+'FF_'+base_name+tile+'_R.tif',mip_r)
            #io.imsave(proc_folder+'FF_'+base_name+tile+'_G.tif',mip_g)
            #io.imsave(proc_folder+'FF_'+base_name+tile+'_B.tif',mip_b)
        cv2.imwrite(proc_folder+timestamp+'_FF_'+base_name+'_W.tif',mip_w)

        print("single stack job done")



if __name__ == "__main__":
    freeze_support()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    start_time = time.time()

    print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
    print('Written by Wesley Wong @ Hsu Lab, Harvard, Department of Stem Cell & Regenerative Biology 1/18/2021\n\
           after getting very frustrated with all the clicking and waiting from the actual software.')
    print('\nThis script takes a folder of images and accompanying .bcf file by the BZ-700 microscope made by Keyence\nand returns a\
        Full Focused (FF) by Maximum Intensity Projection image, stitching together all the tiles\n if thereare tiles present')
    print('\n The tiled images produced by this script are simple edge to edge concatenations without any\nplanar corrections.\
        This tool should be used to quickly stitch and assess images for more precise processing if worthwhile.\n\
            The output FF images can be used by Photoshop, FIJI, etc to stitch better final fusions.')
    print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n')
    target_path = 'foo' #temporary placeholder to avoid null value exception
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        print('ERROR! SEE BELOW AND PLEASE PAY ATTENTION TO THE EXACT SYNTAX INCLUDING SLASHES AND QUOTATION MARKS (SINGLE \nAND DOUBLE ONES)\n')
        sys.exit("Usage: bzimage <path> \n\nEXAMPLE: bzimage '/Users/wesleywong/single-field-zstack copy merge/early jlv bot/'\n\n\
                 the path should point to a folder of micrographs made by BZ-Analyzer\n\
                 containing TIFs of CH1-CH4 (there must be all 4 channels) and the .bcf file\n\
                 the script is now exiting")
    #proc_folder = "/Users/wesleywong/single-field-zstack copy merge/axial/" #this one is a 8x3 ear stitch made with a custom merge area. WORKS.
    #proc_folder = "/Users/wesleywong/single-field-zstack copy merge/P33 CD1/" #this one is a 3x3 stitch made with custom merge area. WORKS.
    #proc_folder = "/Users/wesleywong/single-field-zstack copy merge/early jlv bot/" #20x single image from multipoint. WORKS.
    #proc_folder = "/Users/wesleywong/single-field-zstack copy merge/20X_CD451_CC3_3X5_STD/" #5x3 center-offset image. WORKS.
    proc_folder = target_path

    #remember the camera for the keyence captures the individual color channels as:
    # B (CH1),
    # G (CH2),
    # R (CH3),
    # W (CH4)

    #pseudocolor assignments
    channels = {
                'R':'CH3',
                'G':'CH2',
                'B':'CH1',
                'W':'CH4'
                }



    #get all the single channel tifs
    only_tifs = re.compile(r'.*CH.[.]tif')

    tifs_no_overlays = []
    for file in os.listdir(proc_folder):
        if re.match(only_tifs,file):
            tifs_no_overlays.append(file)

    pp = pprint.PrettyPrinter()
    print('sample file names of the images to be stitched:')
    pp.pprint(tifs_no_overlays[0:5])
    tiles = find_tiles(tifs_no_overlays)

    print('unique tiles found for stitching:')
    pp.pprint(tiles)



    #find all the z-positions
    zpos = re.compile(r'Z\d\d\d')
    unique_z_pos = []
    for file in tifs_no_overlays:
        unique_z_pos.append(re.search(zpos,file).group(0))
    #print('later calculated length of unique z: %d' % len(unique_z_pos))


    #get image family base name
    if tiles != None: #if there are actually tiles to stitch
        image_family_name = re.compile(r'^.*\d\d\d\d\d_Z')
        base_name = re.search(image_family_name, tifs_no_overlays[0]).group(0)[:-7] #without tile or z pos
        print('image series root name: %s' %base_name)
    else:
        image_family_name = re.compile(r'^.*_Z')
        base_name = re.search(image_family_name, tifs_no_overlays[0]).group(0)[:-1] #without tile or z pos
        print('image series root name: %s' %base_name)


    #call main function which includes the minimal multiprocessing component
    main(tiles,unique_z_pos)

    #continue processing from the multiprocess stacked images
    if tiles !=None:
        #get all the single channel tifs
        RE_RGB = re.compile(timestamp+r'.*_FF_.*\d\d\d\d\d_RGB.tif')
        RE_W = re.compile(timestamp+r'.*_FF_.*\d\d\d\d\d_W.tif')

        finished_mips_rgb = []
        for file in os.listdir(proc_folder):
            if re.match(RE_RGB,file):
                finished_mips_rgb.append(proc_folder+file)
        finished_mips_rgb = sorted(finished_mips_rgb)

        finished_mips_w = []
        for file in os.listdir(proc_folder):
            if re.match(RE_W,file):
                finished_mips_w.append(proc_folder+file)
        finished_mips_w = sorted(finished_mips_w)

        print('sample of finished max intensity projections for each tile position:')
        pp.pprint(finished_mips_rgb[0:2])
        pp.pprint(finished_mips_w[0:2])
    else:
        pass




    if tiles != None:
        #extract information from .bcf file

        with zipfile.ZipFile(proc_folder+base_name[:-1]+'.bcf') as myzip:
            #pp.pprint(myzip.infolist())
            lens_info = myzip.read('GroupFileProperty/Lens/properties.xml')
            lens_info = re.search('<LensName.*</LensName>',str(lens_info)).group(0)
            lens_info = re.search('\s\d*x\s',lens_info).group(0)
            lens_info = lens_info[1:-1]
            row_dims = myzip.read('GroupFileProperty/RangeSelection/ImageJointRow/properties.xml')
            row_dims = re.search('\d*</LimitUpper>',str(row_dims)).group(0)
            row_dims = int(row_dims[:-13])+1 #need more sophisticated number finding since it's sometimes double digit
            col_dims = myzip.read('GroupFileProperty/RangeSelection/ImageJointColumn/properties.xml')
            col_dims = re.search('\d*</LimitUpper>',str(col_dims)).group(0)
            col_dims = int(col_dims[:-13])+1 #need more sophisticated number finding since it's sometimes double digit
            print('microscope objective: %s' % lens_info)
            print('imaging tile rows: %s' % row_dims)
            print('imaging tile cols: %s' % col_dims)
    else:
        pass





    if tiles != None:
        overlap_percent = 0.300 +0.005+0.0025 #0.3 works but the stitching scars are noticeable #1-17-21, WW: 0.3075 works best
        fuse_cols_rgb = col_fusion(finished_mips_rgb,row_dims,col_dims,overlap_percent)
        fuse_rows_rgb = row_fusion(fuse_cols_rgb,row_dims,col_dims,overlap_percent) #0.31 for row fusion might be better than .3 both
        cv2.imwrite(proc_folder+timestamp+'_'+str(lens_info)+'_'+str(row_dims)+'X'+str(col_dims)+'_final_fusion_RGB.tif',fuse_rows_rgb)

        fuse_cols_w = col_fusion(finished_mips_w,row_dims,col_dims,overlap_percent)
        fuse_rows_w = row_fusion(fuse_cols_w,row_dims,col_dims,overlap_percent)
        cv2.imwrite(proc_folder+timestamp+'_'+str(lens_info)+'_'+str(row_dims)+'X'+str(col_dims)+'_final_fusion_W.tif',fuse_rows_w)

    else:
        pass



    stop_time = time.time()
    print('took %d seconds' % (stop_time-start_time))






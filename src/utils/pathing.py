import os
from datetime import datetime 
import logging 
import re 
from utils.exifwrapper import ExifWrapper

# -- EXIF 'image_make' in this list get descriptive text <make>_<model>
IMAGE_MAKERS = ['Apple']

logger = logging.getLogger(__name__)

def calculate_target_folder(source, sourcefile, target_date, filing_preference, preserve_folders):
    
    descriptive = extract_descriptive(sourcefile, source.mountpoint, source.exclude_descriptive, preserve_folders)
    
    # -- deriving working values
    year_string = datetime.strftime(target_date, "%Y")
    date_string = datetime.strftime(target_date, "%Y-%m-%d")
    
    logger.info(" - calculating target folder for source target: %s" % source.target)
    
    if filing_preference == 'label' and descriptive:
        return os.path.join(source.target, year_string, descriptive, date_string)
    elif descriptive:
        return os.path.join(source.target, year_string, "%s_%s" %(date_string, descriptive))
    else:
        return os.path.join(source.target, year_string, date_string)
        
def extract_descriptive(sourcefile, mountpoint, exclude_descriptive, preserve_folders):
    descriptive = None
    ew = ExifWrapper(filepath=sourcefile.working_path)
    all_metadata = ew.all_values()
    if 'image_make' in all_metadata and 'image_model' in all_metadata and all_metadata['image_make'] in IMAGE_MAKERS:
        # -- Apple
        # -- iPhone 5
        descriptive = "%s_%s" % (all_metadata['image_make'], all_metadata['image_model'])
    elif mountpoint:
        # -- use preserve_folders count to save that number of parent folders in the source's base path
        # -- the file may be nested deep, and we're by default going to use all folder names between it and the base path for descriptive text search
        # -- but by default, the base path gets chucked
        # -- preserve_folders saves that number of parent folders from the base path
        # --
        # -- /original/path/given/some/interesting/detail/of/file.jpg <= full_path
        # -- /original/path/given/ <= mountpoint
        # -- preserve_folders = 0 ->            some/interesting/detail/of/file.jpg
        # -- preserve_folders = 2 -> path/given/some/interesting/detail/of/file.jpg

        path_to_chuck = mountpoint.rstrip('/')
        for i in range(preserve_folders):
            path_to_chuck = path_to_chuck.rpartition('/')[0]
        base_removed = sourcefile.original_path.replace(path_to_chuck, '') if path_to_chuck else sourcefile.original_path
        descriptive_path = base_removed.rpartition('/')[0]
        logger.debug(" - descriptive path: %s" % descriptive_path)

        # -- remove leading /dupe/nnn
        if re.search('\/?dupe\/[0-9]+', descriptive_path):
            descriptive_path = re.sub("\/?dupe\/[0-9]+", "", descriptive_path)
        descriptive_folders = [ f for f in descriptive_path.split('/') if f ]

        logger.debug(" - descriptive folders: %s" % descriptive_folders)

        descriptive_remove_regexp = ['^[0-9]{8}$', '^[0-9]{4}$', '^[0-9]{4}[-_]{1}[0-9]{2}[-_]{1}[0-9]{2}$']#, '[0-9]{4}-[0-9]{2}-[0-9]{2}']
        if exclude_descriptive and len(exclude_descriptive) > 0:
            descriptive_remove_regexp.extend(exclude_descriptive)
        logger.debug(" - descriptive remove regexps: %s" % ",".join(descriptive_remove_regexp))
        for r in [ r for r in descriptive_remove_regexp if r ]:
            descriptive_folders = [ d for d in descriptive_folders if d and not re.match(r, d) ]

        logger.debug(" - descriptive folders: %s" % descriptive_folders)

        descriptive_sub_regexp = [("[0-9]{4}_[0-9]{2}_[0-9]{2}", " "), ("[0-9]{4}-[0-9]{2}-[0-9]{2}", " "), ("-", " "), ("\s{2,}", " ")]
        logger.debug(" - descriptive sub regexp: %s" % ",".join([ "%s -> \"%s\"" % (s[0], s[1]) for s in descriptive_sub_regexp ]))
        for s in descriptive_sub_regexp:
            descriptive_folders = [ re.sub(s[0], s[1], d).strip() for d in descriptive_folders if d ]

        logger.debug(" - descriptive folders: %s" % descriptive_folders)
        tokens = []
        for d in descriptive_folders:
            tokens.extend([ d.strip().rstrip("_").lstrip("_") for d in d.split(' ') if d ])

        logger.debug(" - tokens: %s" % tokens)

        unique_tokens = []
        for t in tokens:
            if t not in unique_tokens:
                unique_tokens.append(t)

        descriptive = "_".join(unique_tokens) if len(unique_tokens) > 0 else None
        logger.debug(" - descriptive: %s" % ( "'%s'" % descriptive if descriptive else None ))

    return descriptive

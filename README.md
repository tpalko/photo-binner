# photobinner

Sorts image files into a two-level folder structure:  YYYY/YYYY-MM-DD/.

This program does basically one thing, additionally:

* verifies the target date folder with EXIF metadata, the file's modification time, and a possible timestamp in the filename (e.g. IMG_20190118_120533.JPG)
* extracts descriptive text from the original folder structure to include in the final destination folder name
* tracks history to avoid re-copying the same file in future runs
* collects statistics (anomalies/inconsistencies found, source/destination bin counts)
* compares the MD5 hash of supposed duplicates to prevent loss of misnamed files
* works with multiple sources at once to converge at a single destination
* comes with source type implementations supporting Android (adb), block devices, and general folders
* has a pluggable architecture for source types, so you can write your own!
* has a versatile configuration file for easy control over its behavior

## How To

1. Copy the file `pbrc.example` to your home folder as `~/.pbrc`
2. Configure `~/.pbrc`, setting values for you, as a person
3. Run the command to install `photobinner`

```
$ python setup.py install
```

4. Run the command to see `photobinner`'s options:

```
$ photobinner -h
```

5. Say out loud

```
This is software I downloaded from the internet. If I run it, whatever it does is
ultimately nobody's responsibility but my own. I am free to read the code, learning
Python if necessary, to ensure the safety of my files.
```

6. When you're familiar with its options, run it for real:

```
$ photobinner <options>
```

I emphasize inspecting the `--help` because this program is messing with your photos. You know, those
things you make sure to grab before running out of your burning home. (sorry) That said,
there is a `--dry-run` option, and all of the code that actually does anything is contained
within a single conditional block (more or less). _That_ said, with options set in certain
ways, this program will potentially move and modify your files. (Copy is the default.)

## General Operation

* Loads source type implementations
* Loads user-configured sources (flagged with source type name)
* Chooses user sources based on run parameters
* Verifies chosen sources (existence, access, file count)
* For each source:
  * For each file:
    * determines correct timestamp
    * extracts descriptive text
    * checks potential duplicates at destination
    * copies or moves the file, renaming and setting modification time correctly

## Sources

(base model, required fields)

### BlockDevice

(model, required fields)

### Folder

(model, required fields)

### Android

(model, required fields)
(adb key file)

## Design Choices

Possibly worth noting ..

### Exception Handling
### Pluggable Source Type Implementations

## Future Work

- progress bar
- use actual path for session logging
- work in as much processing pre-adb copy (target determination) to skip duplicates before pulling
- flesh out session file lifetime
  - one file for all eternity? this gets big
- flesh out global options vs. per-source
- report each change made / reverse processing
- allow configurable arbitrary path to plugin sources
- broader deduplication
- other fun things to do with image files while we're in there anyway   

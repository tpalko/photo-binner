# photobinner

This program, broadly, does one thing: sorts image files into a two-level folder structure:  YYYY/YYYY-MM-DD/.

Additionally / optionally:

* verifies the target date folder using EXIF metadata, the file's modification time, and a possible timestamp in the filename (e.g. IMG_20190118_120533.JPG)
* includes descriptive text in the destination folder name, extracting the text from the original folder structure
* prevents re-copying files by tracking a history of processed files
* collects statistics (anomalies/inconsistencies found, source/destination bin counts)
* compares the MD5 hash of supposed duplicates to prevent loss of misnamed files
* works with multiple sources at once to converge at a single destination, supporting Android (adb), block devices, and general folders out of the box
* has a pluggable architecture for source types, so you can write your own!
* has a versatile configuration file for easy control over its behavior

## Who Is This For?

You, if:

* you have multiple sources of photo files (SD cards, smartphone, old archives of files)
* you have disorganized old files, maybe with incorrect timestamps
* you want all your images in one place
* the default photo import workflow offered by your OS isn't cutting it

This program solves the problem of disparate photo file sources, treating your SD card and your phone
as equals - with one command, photos are copied from both and date-sorted into a single tree at a location
of your choice, where you can treat them how you like.

It's also great for organizing that hodgepodge of image files you've been amassing for years - with some
files in folders named for an event, some with the date, and they've all lost their original modification
timestamp copying from old systems.

This program does not:

* display images
* tag images
* share images

## How To

### Prerequisites

#### A Note About adb (Android Debug Bridge)

*A note about noting adb:*
`photobinner` started out just sorting files between folders. This is still _the_
primary supported use case, and if this satisfies you, stick with that and don't
worry about `adb`. If rolling your smartphone into your photo library
curating process is a priority for you, read on.

*`photobinner` is tested on GNU/Linux distributions. There has been absolutely zero testing on Mac or Windows.*

Your Android smartphone can be accessed by `photobinner` from your Linux computer using
`adb`, the Android Debug Bridge. For Android 4.2.2 and up, this access will require an RSA keypair.

The Python module `adb` is available through PyPi. If you want the command-line
`adb` tool, this is available with the `adb` package, at least on Debian Stretch. Installing
`adb` will also give you `android-sdk-platform-tools-common`, which contains the udev
rules for Android devices. Command-line `adb` is probably necessary to generate
the requisite keypair. I haven't done a full, clean system test to determine
exactly what is necessary, but if you install the `adb` package, can run `adb devices`
and see your device listed, and can run `adb shell` successfully, then `photobinner`
will likely not have a problem. Before trying to generate the keys, just run the `adb`
commands to see what happens - it may generate what it needs automatically.

#### Initial Install and Configuration

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

_NOTE: Python dependencies should be installed along with `photobinner`, however if
you find missing packages when running it, these can be installed manually with
`pip install -r requirements.txt`_

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

## Source Types

A _source type_ is the general class of thing from which your photos are read. Different source types require different methods of reading, copying, and generally handling your files. For instance, a block device that represents your SD card will need to be mounted before accessing it, whereas a folder can simply be read. An Android device requires a special library. Currently, the `photo-binner` project ships with these three aforementioned source type implementations. This is a pluggable architecture, and should you want to write an implementation for yet another source type, you are welcome to do so (in Python), and `photobinner` will happily talk to it.

The base class for source type implementations is `photobinner.source.Source`. This class has abstract methods which must be implemented, save for `sigint_handler()`, which must be implemented but may return `None` if your source has no need for knowing about `signal.SIGINT` (Ctrl-C). The base class also has helper functions which define some common, default behavior such as a path-walking generator.

Aside from including a new source type in the `sources` folder, `sources/__init__.py` must be modified to advertise it.

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

## Bugs

- when multiple sources validate, the message after selecting a session only reports counts for one of them. verify
how the session file is parsed when selected and that all sources are accounted for properly.
- '001' added to exclude_descriptive command line parameter doesn't remove this from descriptive text
- history tracking to avoid re-copying the same file does not account for device-assigned file number rollover IMG_9999.JPG, IMG_0000.JPG, ..
- detection of "double timezoning" may be generating false positives

## Verify Complete

- use actual path for session logging

## Future Work

- broader deduplication
  - incorporate light database to index hash sums for more thorough duplicate identification
  - provide duplicate finding as a primary operation
- progress bar
- work in as much processing pre-adb copy (target determination) to skip duplicates before pulling
- flesh out session file lifetime
  - one file for all eternity? this gets big
- flesh out global options vs. per-source
- record all file modifications / provide "undo" operation
- allow configurable arbitrary path to plugin sources
- other fun things to do with image files while we're in there anyway   
- python 3!
- add 'session name' parameter to metadata
- session filename timestamp in metadata

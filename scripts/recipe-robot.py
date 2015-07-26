#!/usr/bin/env python
# This Python file uses the following encoding: utf-8

# Recipe Robot
# Copyright 2015 Elliot Jordan, Shea G. Craig
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
recipe-robot.py

Easily and automatically create AutoPkg recipes.

usage: recipe-robot.py [-h] [-v] input_path [-o output_path] [-t recipe_type]

positional arguments:
    input_path            Path to a recipe or app you'd like to use as the
                          basis for creating AutoPkg recipes.

optional arguments:
    -h, --help            Show this help message and exit.
    -v, --verbose         Generate additional output about the process.
                          Verbose mode is off by default.
    -o, --output          Specify the folder in which to create output recipes.
                          This folder is ~/Library/Caches/Recipe Robot by
                          default.
    -t, --recipe-type     Specify the type(s) of recipe to create.
                          (e.g. download, pkg, munki, jss)
"""


import argparse
import os.path
import plistlib
from pprint import pprint
import random
import shlex
from subprocess import Popen, PIPE
import sys


# Global variables.
version = '0.0.1'
debug_mode = True  # set to True for additional output
prefs_file = os.path.expanduser(
    "~/Library/Preferences/com.elliotjordan.recipe-robot.plist")
prefs = {}

# Build the recipe format offerings.
# TODO(Elliot): This should probably not be a global variable.
avail_recipe_types = (
    ("download", "Downloads an app in whatever format the developer "
                 "provides."),
    ("munki", "Imports into your Munki repository."),
    ("pkg", "Creates a standard pkg installer file."),
    ("install", "Installs the app on the computer running AutoPkg."),
    ("jss", "Imports into your Casper JSS and creates necessary groups, "
            "policies, etc."),
    ("absolute", "Imports into your Absolute Manage server."),
    ("sccm", "Imports into your SCCM server."),
    ("ds", "Imports into your DeployStudio Packages folder.")
)

# Build the list of download formats we know about.
# TODO: It would be great if we didn't need this list, but I suspect we do need
# it in order to tell the recipes which Processors to use.
# TODO(Elliot): This should probably not be a global variable.
supported_download_formats = ("dmg", "zip", "tar.gz", "gzip", "pkg")

# Build the list of existing recipes.
# Example: ['Firefox.download.recipe']
# TODO(Elliot): This should probably not be a global variable.
existing_recipes = []

# Build the dict of buildable recipes and their corresponding
# templates. Example: {'Firefox.jss.recipe': 'pkg.jss.recipe'}
# TODO(Elliot): This should probably not be a global variable.
buildable_recipes = {}

# The name of the app for which a recipe is being built.
# TODO(Elliot): This should probably not be a global variable.
app_name = ""


class bcolors:

    """Specify colors that are used in Terminal output."""

    BOLD = '\033[1m'
    DEBUG = '\033[95m'
    ENDC = '\033[0m'
    ERROR = '\033[91m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    UNDERLINE = '\033[4m'
    WARNING = '\033[93m'


class InputType(object):

    """Python pseudo-enum for describing types of input."""

    (app,
     download_recipe,
     munki_recipe,
     pkg_recipe,
     install_recipe,
     jss_recipe,
     absolute_recipe,
     sccm_recipe,
     ds_recipe) = range(9)


def get_exitcode_stdout_stderr(cmd):
    """Execute the external command and get its exitcode, stdout and stderr."""

    args = shlex.split(cmd)
    # TODO(Elliot): I've been told Popen is not a good practice. Better idea?
    proc = Popen(args, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate()
    exitcode = proc.returncode
    return exitcode, out, err


def build_argument_parser():
    """Build and return the argument parser for Recipe Robot."""

    parser = argparse.ArgumentParser(
        description="Easily and automatically create AutoPkg recipes.")
    parser.add_argument(
        "input_path",
        help="Path to a recipe or app to use as the basis for creating AutoPkg recipes.")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Generate additional output about the process.")
    # TODO(Elliot): Add --plist argument to header info up top.
    parser.add_argument(
        "--plist",
        action="store_true",
        help="Output all results as plists.")
    parser.add_argument(
        "-o", "--output",
        action="store",
        help="Path to a folder you'd like to save your generated recipes in.")
    parser.add_argument(
        "-t", "--recipe-type",
        action="store",
        help="The type(s) of recipe you'd like to generate.")
    return parser


def print_welcome_text():
    """Print the text that people see when they first start Recipe Robot."""

    welcome_text = """
     -----------------------------------
    |  Welcome to Recipe Robot v%s.  |
     -----------------------------------
               \   _[]_
                \  [oo]
                  d-||-b
                    ||
                  _/  \_
    """ % version

    print welcome_text


def init_prefs():
    """Read from preferences plist, if it exists."""

    # If prefs file exists, try to read from it.
    if os.path.isfile(prefs_file):

        # Open the file.
        try:
            prefs = plistlib.readPlist(prefs_file)
        except Exception:
            print("There was a problem opening the prefs file. "
                  "Building new preferences.")
            prefs = build_prefs(prefs)

    else:
        print "No prefs file found. Building new preferences..."
        prefs = build_prefs(prefs)

    # Record last version number.
    prefs["LastRecipeRobotVersion"] = version

    # Write preferences to plist.
    plistlib.writePlist(prefs, prefs_file)

    return prefs


def build_prefs(prefs):
    """Prompt user for preferences, then save them back to the plist."""

    # TODO(Elliot): Make this something users can come back to and modify,
    # rather than just a first-run thing.

    # Prompt for and save recipe identifier prefix.
    prefs["RecipeIdentifierPrefix"] = "com.github.homebysix"
    print "\nRecipe identifier prefix"
    print "[description of what that means]\n"
    choice = raw_input(
        "Please type your preferred recipe identifier prefix [%s]: " % prefs["RecipeIdentifierPrefix"])
    prefs["RecipeIdentifierPrefix"] = choice

    # Prompt for recipe creation location.
    prefs["RecipeCreateLocation"] = "~/Library/AutoPkg/RecipeOverrides"
    print "\nLocation to save new recipes"
    print "[description of what that means]\n"
    choice = raw_input(
        "Please type your new recipe location [%s]: " % prefs["RecipeCreateLocation"])
    prefs["RecipeCreateLocation"] = choice

    # Start with all available recipe types on.
    prefs["RecipeTypes"] = {}
    i = 0
    for i in range(0, len(avail_recipe_types)):
        prefs["RecipeTypes"][avail_recipe_types[i][0]] = True
        i += 1
    print "\nPreferred recipe types"
    print "[description of what that means]\n"

    # Prompt to set recipe types on/off as desired.
    while True:
        i = 0
        for i in range(0, len(avail_recipe_types)):
            if prefs["RecipeTypes"][avail_recipe_types[i][0]] is False:
                indicator = " "
            else:
                indicator = "*"
            print "  [%s] %s. %s - %s" % (indicator, i, avail_recipe_types[i][0], avail_recipe_types[i][1])
            i += 1
        choice = raw_input(
            "\nType a number to toggle the corresponding recipe "
            "type between ON [*] and OFF [ ]. When you're satisfied "
            "with your choices, type an S to save and proceed: ")
        if choice.upper() == "S":
            break
        else:
            try:
                if prefs["RecipeTypes"][avail_recipe_types[int(choice)][0]] is False:
                    prefs["RecipeTypes"][
                        avail_recipe_types[int(choice)][0]] = True
                else:
                    prefs["RecipeTypes"][
                        avail_recipe_types[int(choice)][0]] = False
            except Exception:
                print "%sInvalid choice. Please try again.%s\n" % (bcolors.ERROR, bcolors.ENDC)

    # TODO(Elliot): Make this interactive while retaining scrollback.
    # Maybe with curses module?

    return prefs


def increment_recipe_count(prefs):
    """Add 1 to the cumulative count of recipes created by Recipe Robot."""

    prefs = plistlib.readPlist(prefs_file)
    prefs["RecipeCreateCount"] += 1
    plistlib.writePlist(prefs, prefs_file)


def get_input_type(input_path):
    """Determine the type of recipe generation needed based on path.

    Args:
        input_path: String path to an app, download recipe, etc.

    Returns:
        Int pseudo-enum value of InputType.
    """

    if input_path.endswith(".app"):
        return InputType.app
    elif input_path.endswith(".download.recipe"):
        return InputType.download_recipe
    elif input_path.endswith(".munki.recipe"):
        return InputType.munki_recipe
    elif input_path.endswith(".pkg.recipe"):
        return InputType.pkg_recipe
    elif input_path.endswith(".install.recipe"):
        return InputType.install_recipe
    elif input_path.endswith(".jss.recipe"):
        return InputType.jss_recipe
    elif input_path.endswith(".absolute.recipe"):
        return InputType.absolute_recipe
    elif input_path.endswith(".sccm.recipe"):
        return InputType.sccm_recipe
    elif input_path.endswith(".ds.recipe"):
        return InputType.ds_recipe


def create_existing_recipe_list(app_name):
    """Use autopkg search results to build existing recipe list."""

    # TODO(Elliot): Suggest users create GitHub API token to prevent limiting.
    # TODO(Elliot): Do search again without spaces in app names.
    # TODO(Elliot): Match results for apps with "!" in names. (e.g. Paparazzi!)
    cmd = "autopkg search -p %s" % app_name
    exitcode, out, err = get_exitcode_stdout_stderr(cmd)
    if exitcode == 0:
        for line in out.split("\n"):
            if ".recipe" in line:
                # Add the first "word" of each line of search results. Example:
                # Firefox.pkg.recipe
                existing_recipes.append(line.split(None, 1)[0])
    else:
        print err
        sys.exit(exitcode)


def create_buildable_recipe_list(app_name):
    """Add any recipe types that don't already exist to the buildable list."""

    pprint(prefs) # why is this still {}?
    for recipe_format, is_included in prefs["RecipeTypes"].iteritems():
        if is_included is True:
            if "%s.%s.recipe" % (app_name, recipe_format) not in existing_recipes:
                buildable_recipes[
                    # TODO(Elliot): Determine proper template to use.
                    app_name + "." + recipe_format + ".recipe"
                ] = "template TBD"


def handle_app_input(input_path):
    """Process an app, gathering required information to create a recipe."""

    # Figure out the name of the app.
    try:
        info_plist = plistlib.readPlist(input_path + "/Contents/Info.plist")
        app_name = info_plist["CFBundleName"]
        create_existing_recipe_list(app_name)
    except KeyError:
        try:
            app_name = info_plist["CFBundleExecutable"]
            create_existing_recipe_list(app_name)
        except KeyError:
            print "%s[ERROR] Sorry, I can't figure out what this app is called.%s" % (
                bcolors.ERROR, bcolors.ENDC
            )
            sys.exit(1)

    # Check for a Sparkle feed, but only if a download recipe doesn't exist.
    if app_name + "%s.download.recipe" not in existing_recipes:
        try:
            # TODO(Elliot): Only add to buildable if download recipe doesn't
            # already exist.
            buildable_recipes[
                app_name + ".download.recipe"
            ] = "download-from-sparkle.recipe"

        except KeyError:
            try:
                # TODO(Elliot): Only add to buildable if download recipe doesn't
                # already exist.
                buildable_recipes[app_name + ".download.recipe"] = (
                    "download-from-sparkle.recipe"
                )

                # TODO(Elliot): There was no existing download recipe, but if
                # we have a Sparkle feed, we now know we can build one.
                # However, we don't know what format the resulting download
                # will be. We need to find that out before we can create
                # recipes that use the download as a parent.

            except KeyError:
                print "%s[WARNING] No Sparkle feed.%s" % (bcolors.WARNING,
                                                          bcolors.ENDC)
                search_sourceforge_and_github(app_name)

    else:

        # TODO(Elliot): We know that there's an existing download recipe
        # available, but we don't know what format the resulting
        # download is. We need to find that out before we can
        # create recipes that use the download as a parent.
        pass

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # If munki recipe is buildable, the minimum OS version prove useful.
    # TODO(Elliot): Find a way to pass variables like this to the generator.
    if app_name + ".munki.recipe" in buildable_recipes:
        try:
            min_sys_vers = info_plist["LSMinimumSystemVersion"]
        except KeyError:
            if debug_mode:
                print("%s[WARNING] can't detect minimum system version "
                      "requirement.%s" % (bcolors.DEBUG, bcolors.ENDC))


def handle_download_recipe_input(input_path):
    """Process a download recipe, gathering information useful for building
    other types of recipes.
    """

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Get the download file format.
    # TODO(Elliot): Parse the recipe properly. Don't use grep.
    parsed_download_format = ""
    for download_format in supported_download_formats:
        cmd = "grep '.%s</string>' '%s'" % (download_format, input_path)
        exitcode, out, err = get_exitcode_stdout_stderr(cmd)
        if exitcode == 0:
            print "Looks like this recipe downloads a %s." % download_format
            parsed_download_format = download_format
            break

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # Attempting to simultaneously determine which recipe types are
    # available to build and which templates we should use for each.
    # TODO(Elliot): Make it better. Integrate with existing
    # create_buildable_recipe_list function.
    for recipe_format in avail_recipe_types:
        if app_name + "." + recipe_format + ".recipe" not in existing_recipes:
            this_recipe_type = "%s.%s.recipe" % app_name, recipe_format
            if recipe_format in ("pkg", "install", "munki"):
                this_recipe_template = "%s-from-download_%s" % recipe_format, download_format
                buildable_recipes[this_recipe_type] = this_recipe_template
            else:
                this_recipe_template = "%s-from-pkg" % recipe_format
                buildable_recipes[this_recipe_type] = this_recipe_template

    # Offer to build pkg, munki, jss, etc.


def handle_munki_recipe_input(input_path):
    """Process a munki recipe, gathering information useful for building other
    types of recipes."""

    # Determine whether there's already a download Parent recipe.
    # If not, add it to the list of offered recipe formats.

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # If this munki recipe both downloads and imports the app, we
    # should offer to build a discrete download recipe with only
    # the appropriate sections of the munki recipe.

    # Offer to build pkg, jss, etc.

    # TODO(Elliot): Think about whether we want to dig into OS requirements,
    # blocking applications, etc when building munki recipes. I vote
    # yes, but it's probably not going to be easy.


def handle_pkg_recipe_input(input_path):
    """Process a pkg recipe, gathering information useful for building other
    types of recipes."""

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # Check to see whether the recipe has a download recipe as its parent. If
    # not, offer to build a discrete download recipe.

    # Offer to build munki, jss, etc.


def handle_install_recipe_input(input_path):
    """Process an install recipe, gathering information useful for building
    other types of recipes."""

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # Check to see whether the recipe has a download and/or pkg
    # recipe as its parent. If not, offer to build a discrete
    # download and/or pkg recipe.

    # Offer to build other recipes as able.


def handle_jss_recipe_input(input_path):
    """Process a jss recipe, gathering information useful for building other
    types of recipes."""

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # Check to see whether the recipe has a download and/or pkg
    # recipe as its parent. If not, offer to build a discrete
    # download and/or pkg recipe.

    # Offer to build other recipes as able.


def handle_absolute_recipe_input(input_path):
    """Process an absolute recipe, gathering information useful for building
    other types of recipes.
    """

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # Check to see whether the recipe has a download and/or pkg
    # recipe as its parent. If not, offer to build a discrete
    # download and/or pkg recipe.

    # Offer to build other recipes as able.


def handle_sccm_recipe_input(input_path):
    """Process a sccm recipe, gathering information useful for building other
    types of recipes."""

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # Check to see whether the recipe has a download and/or pkg
    # recipe as its parent. If not, offer to build a discrete
    # download and/or pkg recipe.

    # Offer to build other recipes as able.


def handle_ds_recipe_input(input_path):
    """Process a ds recipe, gathering information useful for building other
    types of recipes."""

    # Read the recipe as a plist.
    input_recipe = plistlib.readPlist(input_path)

    # Get the app's name from the recipe.
    app_name = input_recipe["Input"]["NAME"]

    # Use the autopkg search results to build a list of existing recipes.
    create_existing_recipe_list(app_name)

    # If an available recipe type doesn't already exist, add to the buildable
    # recipes list.
    create_buildable_recipe_list(app_name)

    # Check to see whether the recipe has a download and/or pkg
    # recipe as its parent. If not, offer to build a discrete
    # download and/or pkg recipe.

    # Offer to build other recipes as able.


def search_sourceforge_and_github(app_name):
    """For apps that do not have a Sparkle feed, try to locate their project
    information on either SourceForge or GitHub so that the corresponding
    URL provider processors can be used to generate a recipe.
    """

    # TODO(Shea): Search on SourceForge for the project.
    #     If found, pass the project ID back to the recipe generator.
    #     To get ID: https://gist.github.com/homebysix/9640c6a6eecff82d3b16
    # TODO(Shea): Search on GitHub for the project.
    #     If found, pass the username and repo back to the recipe generator.


def generate_download_recipe(keys):
    """Generate a download recipe."""

    # TODO(Elliot): Some of these keys, like MinimumVersion, should be stored
    # centrally rather than referenced in every generate_X_recipe function.

    if "sparkle_url" in keys:
        plist_object = dict(
            Identifier="%s.download.%s" % (prefs["RecipeIdentifierPrefix"], keys["app_name"]),
            Description="Downloads the latest version of %s." % keys["app_name"],
            MinimumVersion="0.5.0",
            Input=dict(
                NAME=keys["app_name"],
                SPARKLE_FEED_URL=keys["sparkle_url"]),
            Process=[
                dict(
                    Processor="SparkleUpdateInfoProvider",
                    Arguments=dict(
                        appcast_url="%SPARKLE_FEED_URL%")),
                dict(
                    Processor="URLDownloader",
                    Arguments=dict(
                        filename=">%NAME%.dmg")),
                dict(
                    Processor="EndOfCheckPhase"),
            ])
        write_recipe_file(plist_object)

    elif "github_repo" in keys:
        plist_object = dict(
            Identifier="%s.download.%s" % (prefs["RecipeIdentifierPrefix"], keys["app_name"]),
            Description="Downloads the latest release of %s from GitHub." % keys["app_name"],
            MinimumVersion="0.5.0",
            Input=dict(
                NAME=keys["app_name"]),
            Process=[
                dict(
                    Processor="",
                    Arguments=dict(
                        key="value")),
                dict(
                    Processor="",
                    Arguments=dict(
                        key="value")),
            ])
        write_recipe_file(plist_object)

    elif "sourceforge_group_id" in keys:
        plist_object = dict(
            Identifier="%s.download.%s" % (prefs["RecipeIdentifierPrefix"], keys["app_name"]),
            Description="Downloads the latest release of %s from SourceForge." % keys["app_name"],
            MinimumVersion="0.5.0",
            Input=dict(
                NAME=keys["app_name"]),
            Process=[
                dict(
                    Processor="",
                    Arguments=dict(
                        key="value")),
                dict(
                    Processor="",
                    Arguments=dict(
                        key="value")),
            ])
        write_recipe_file(plist_object)

    else:
        print "%s[ERROR] Unable to create download recipe.%s" % (bcolors.ERROR, bcolors.ENDC)



def generate_munki_recipe(keys):
    """Generate a munki recipe."""

    # We'll use this later when creating icons for Munki and JSS recipes.
    # cmd = 'sips -s format png \
    # "/Applications/iTunes.app/Contents/Resources/iTunes.icns" \
    # --out "/Users/elliot/Desktop/iTunes.png" \
# --resampleHeightWidthMax 128'

    plist_object = dict(
        Identifier="%s.munki.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Imports the latest version of %s into Munki." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def generate_pkg_recipe(keys):
    """Generate a pkg recipe."""

    plist_object = dict(
        Identifier="%s.pkg.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Downloads the latest version of %s and creates a package." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def generate_install_recipe(keys):
    """Generate a install recipe."""

    plist_object = dict(
        Identifier="%s.install.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Installs the latest version of %s." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def generate_jss_recipe(keys):
    """Generate a jss recipe."""

    # We'll use this later when creating icons for Munki and JSS recipes.
    # cmd = 'sips -s format png \
    # "/Applications/iTunes.app/Contents/Resources/iTunes.icns" \
    # --out "/Users/elliot/Desktop/iTunes.png" \
    # --resampleHeightWidthMax 128'

    plist_object = dict(
        Identifier="%s.jss.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Imports the latest version of %s into your JSS." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def generate_absolute_recipe(keys):
    """Generate a absolute recipe."""

    plist_object = dict(
        Identifier="%s.absolute.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Imports the latest version of %s into Absolute Manage." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def generate_sccm_recipe(keys):
    """Generate a sccm recipe."""

    plist_object = dict(
        Identifier="%s.sccm.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Imports the latest version of %s into SCCM." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def generate_ds_recipe(keys):
    """Generate a ds recipe."""

    plist_object = dict(
        Identifier="%s.ds.%s" % (prefs["RecipeIdentifierPrefix"], app_name),
        Description="Imports the latest version of %s into DeployStudio." % app_name,
        MinimumVersion="0.5.0",
        Input=dict(
            NAME=keys["app_name"]),
        Process=[
            dict(
                Processor="SomeProcessor",
                Arguments=dict(
                    key="value"))
        ])
    write_recipe_file(plist_object)


def write_recipe_file(plist_object):
    """Write a generated recipe to disk."""

    plist_path = prefs["RecipeCreateLocation"]
    recipe_file = os.path.expanduser(plist_path)
    plistlib.writePlist(plist_object, recipe_file)
    print "Wrote to: " + plist_path
    increment_recipe_count(prefs)
    congrats_msg = (
        "That's awesome!",
        "Amazing.",
        "Well done!",
        "Good on ya!",
        "Thanks!",
        "Pretty cool, right?",
        "You rock star, you.",
        "Fantastic."
    )
    print "You've now created %s recipes with Recipe Robot. %s" % (prefs["RecipeCreateCount"], random.choice(congrats_msg))


def print_debug_info():
    """Print current debug information."""

    print bcolors.DEBUG
    print "\n    RECIPE IDENTIFIER PREFIX: \n"
    print prefs["RecipeIdentifierPrefix"]
    print "\n    PREFERRED RECIPE TYPES\n"
    pprint(prefs["RecipeTypes"])
    print "\n    AVAILABLE RECIPE TYPES\n"
    pprint(avail_recipe_types)
    print "\n    SUPPORTED DOWNLOAD FORMATS\n"
    pprint(supported_download_formats)
    print "\n    CURRENT APP NAME\n"
    pprint(app_name)
    print "\n    EXISTING RECIPES\n"
    pprint(existing_recipes)
    print "\n    BUILDABLE RECIPES\n"
    pprint(buildable_recipes)
    print bcolors.ENDC


# TODO(Elliot): Make main() shorter. Just a flowchart for the logic.
def main():
    """Make the magic happen."""

    print_welcome_text()

    argparser = build_argument_parser()
    args = argparser.parse_args()

    # Temporary argument handling
    input_path = args.input_path
    input_path = input_path.rstrip("/ ")

    # TODO(Elliot): Verify that the input path actually exists.
    if not os.path.exists(input_path):
        print "%s[ERROR] Input path does not exist. Please try again with a valid input path.%s" % (
            bcolors.ERROR, bcolors.ENDC
        )
        sys.exit(1)

    prefs = init_prefs()

    input_type = get_input_type(input_path)
    print "\nProcessing %s ..." % input_path

    # Orchestrate helper functions to handle input_path's "type".
    if input_type is InputType.app:
        handle_app_input(input_path)
    elif input_type is InputType.download_recipe:
        handle_download_recipe_input(input_path)
    elif input_type is InputType.munki_recipe:
        handle_munki_recipe_input(input_path)
    elif input_type is InputType.pkg_recipe:
        handle_pkg_recipe_input(input_path)
    elif input_type is InputType.install_recipe:
        handle_install_recipe_input(input_path)
    elif input_type is InputType.jss_recipe:
        handle_jss_recipe_input(input_path)
    elif input_type is InputType.absolute_recipe:
        handle_absolute_recipe_input(input_path)
    elif input_type is InputType.sccm_recipe:
        handle_sccm_recipe_input(input_path)
    elif input_type is InputType.ds_recipe:
        handle_ds_recipe_input(input_path)
    else:
        print("%s[ERROR] I haven't been trained on how to handle this input "
              "path:\n    %s%s" % (bcolors.ERROR, input_path, bcolors.ENDC))
        sys.exit(1)

    print_debug_info()

    # Prompt the user with the available recipes types and let them choose.
    print "\nHere are the recipe types available to build:"
    for key, value in buildable_recipes.iteritems():
        print "    %s" % key

    # Generate selected recipes.
    # generate_recipe("", dict())


if __name__ == '__main__':
    main()

# pikaur

AUR helper with minimal dependencies. Review PKGBUILDs all in once, next build them all without user interaction.

Inspired by `pacaur`, `yaourt` and `yay`.

Instead of trying to be smarter than pacman (by using `--nodeps`, `--force`, `--noconfirm` and so) it just interactively tells pacman what to do. If pacman will ask some unexpected question user will be just able to answer it manually.

If some `pacman` or `makepkg` operation failed for irrelevant reason (like timed out `sudo` prompt) pikaur will suggest to restart the operation and instead of failing the whole transaction you could also skip the failed operation.

The following pacman operations are extended with AUR capabilities:

* `-S` (build AUR packages, `--needed`, `--ignore` and `--noconfirm` are supported as in pacman, other args are just bypassed to it)
* `-Sw` (build AUR packages but not install)
* `-Ss` (search or list all AUR packages, `-q` also supported)
* `-Si` (package info)
* `-Su` / `-Syu` (sysupgrade)
* `-Sc` / `-Scc` (build dir /built packages cache clean)
* `-Qu` (query upgradeable, `-q` supported)

Also see `pikaur -Sh` and `pikaur -Qh` for pikaur-specific flags.

Pikaur wraps all the pacman options accurately except for `-Syu` which is being splitted into `-Sy` (to refresh package list first) and `-Su` (to install upgrades after user confirmed the package list or has been altered it via [M]anual package selection).

* [Installation](#installation "")
* [Run without installation](#run-without-installation "")
* [Config file](#configuration "")
* [Directories](#directories "")
* [FAQ](#faq "")
* [Contributing](#contributing "")
* - [Translations](#translations "")

![Screenshot](https://github.com/actionless/pikaur/blob/master/screenshots/package_update.png "Screenshot")


### Installation

```sh
sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/pikaur.git
cd pikaur
makepkg -fsri
```


### Run without installation

```sh
git clone https://github.com/actionless/pikaur.git
cd pikaur
python3 ./pikaur.py -Ss AUR_PACKAGE_NAME
python3 ./pikaur.py -S AUR_PACKAGE_NAME
python3 ./pikaur.py -Syu
```



### Configuration

~/.config/pikaur.conf


#### [sync]

##### DevelPkgsExpiration (default: -1)
when doing sysupgrade count all devel (-git, -svn, -bzr, -hg, -cvs) packages older than N days as being upgradeable.
-1 disables this.
0 means always upgrade.
Passing `--devel` argument will override this option to 0.

##### AlwaysShowPkgOrigin (default: no)
when installing new packages show their repository name even if they are coming from one of the official Arch Linux repositories.

##### UpgradeSorting (default: versiondiff)
when upgrading packages sort them by `versiondiff`, `pkgname` or `repo`.


#### [build]

##### KeepBuildDir (default: no)
don't remove `~/.cache/pikaur/build/${PACKAGE_NAME}` directory between the builds.

##### NoEdit (default: no)
don't prompt to edit PKGBUILD and install files.

##### NoDiff (default: no)
don't prompt to show the build files diff.

#### [colors]

terminal colors, from 0 to 15

##### Version (default: 10)
##### VersionDiffOld (default: 11)
##### VersionDiffNew (default: 9)


#### [ui]

##### RequireEnterConfirm (default: yes)
require enter key to be pressed when answering questions.


#### [misc]

##### PacmanPath (default: pacman)
path to pacman executable.






### Directories

```sh
~/.cache/pikaur/
├── aur_repos/  # keep there aur repos; show diff when updating
│   └── last_installed.txt  # aur repo hash of last successfully installed package
├── build/  # build directory (removed after successfull build)
└── pkg/  # built packages directory
~/.config/pikaur.conf  # config file
```

### FAQ

##### How to upgrade all the dev (-git) packages at once?

`pikaur -Syu --devel --needed --keepbuild`

`--needed` option will make sure what the same package version won't be rebuilt again
and `--keepbuild` option will help to avoid re-downloading whole git repo of each installed dev package.

##### How to avoid manually importing GPG keys?

It's recommended to control the keys manually. However if you know what you doing, `keyserver-options auto-key-retrieve` GPG option will automatically import GPG keys.

Note what `makepkg` is using user's keyring, not `pacman`'s one.

##### How to override default source directory, build directory or built package destination?

Set `SRCDEST`, `BUILDDIR` or `PKGDEST` accordingly in `makepkg.conf`.

For more info see `makepkg` documentation.

##### Hot to clean old or uninstalled AUR packages in ~/.cache/pikaur/pkg?

This is the part from a pacman-hook (paccache-clear.hook). For both official and AUR packages, the last 3 packages are kept if the package is still installed, and one package is kept if the package is uninstalled.

```
Exec = /usr/bin/env bash -c "/usr/bin/paccache -vrk3; /usr/bin/paccache -vruk1; /usr/bin/paccache --cachedir PATH/TO/.cache/pikaur/pkg/ -vrk3; /usr/bin/paccache --cachedir PATH/TO/.cache/pikaur/pkg/ -vruk1"
```

Change the numbers, and you are good to go.


### Contributing


#### Code

You can start from [this list of issues](https://github.com/actionless/pikaur/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22 ""). Grep-ing `@TODO` comments also useful if you're itching to write something.


#### Translations

To start working on a new language, say 'es' (Spanish), add it to the
`Makefile` `LANGS` variable and run `make`. Then translate `locale/es.po` using
your favorite PO editor. Run `make` every time the Python code strings change
or the `.po` is modified.

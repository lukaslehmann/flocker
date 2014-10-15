# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Helper utilities for the Flocker packaging
"""

import sys
from subprocess import check_call
from tempfile import mkdtemp

from twisted.python.filepath import FilePath
from twisted.python import usage

from characteristic import attributes

import flocker

from .release import make_rpm_version


@attributes(['steps'])
class BuildSequence(object):
    """
    Run the supplied `steps` in consecutively.
    """
    def run(self):
        for step in self.steps:
            step.run()


@attributes(['target_path'])
class InstallVirtualEnv(object):
    """
    Install a virtualenv in the supplied `target_path`.

    We call ``virtualenv`` as a subprocess rather than as a library, so that we
    can turn off Python byte code compilation.
    """
    def run(self):
        check_call(
            ['virtualenv', '--quiet', '--system-site-packages', self.target_path.path],
            env=dict(PYTHONDONTWRITEBYTECODE='1')
        )


@attributes(['virtualenv_path', 'package_uri'])
class InstallApplication(object):
    """
    Install the supplied `package_uri` using `pip` from the supplied
    `virtualenv_path`.
    """
    def run(self):
        pip_path = self.virtualenv_path.child('bin').child('pip').path
        check_call(
            [pip_path, '--quiet', 'install', self.package_uri]
        )
        check_call(
            ['virtualenv', '--quiet', '--relocatable', self.virtualenv_path.path],
            env=dict(PYTHONDONTWRITEBYTECODE='1')
        )


@attributes(['virtualenv_path'])
class GetApplicationVersion(object):
    """
    """
    version = None

    def run(self):
        """
        """
        pip_path = self.virtualenv_path.child('bin').child('pip').path
        check_call([pip_path, 'freeze'])



@attributes(
    ['destination_path', 'source_path', 'name', 'prefix', 'epoch',
     'rpm_version', 'license', 'url', 'vendor', 'maintainer', 'architecture',
     'description'])
class BuildRpm(object):
    """
    Use `fpm` to build an RPM file from the supplied `source_path`.
    """
    def run(self):
        """
        """
        architecture = self.architecture
        if architecture is None:
            architecture = 'all'

        check_call([
            'fpm',
            '-s', 'dir',
            '-t', 'rpm',
            '--package', self.destination_path.path,
            '--name', self.name,
            '--prefix', self.prefix.path,
            '--version', self.rpm_version.version,
            '--epoch', self.epoch,
            '--iteration', self.rpm_version.release,
            '--license', self.license,
            '--url', self.url,
            '--vendor', self.vendor,
            '--maintainer', self.maintainer,
            '--architecture', architecture,
            '--description', self.description,
            '--exclude', '*.pyc',
            '.'], cwd=self.source_path.path
        )


def sumo_rpm_builder(destination_path, package_uri, version, target_dir=None):
    """
    Build an RPM file containing the supplied `package` and all its
    dependencies.

    Motivation:
    * We depend on libraries which are not packaged for the target OS.
    * We depend on newer versions of libraries which have not yet been included
      in the target OS.

    Disadvantages:
    * We won't be able to take advantage of library security updates shipped by
      the target OS.
      * But by shipping our own separate dependency packages we will need to be
        responsible for shipping security patches in those packages.
      * And rather than being responsible only for the security of Flocker, we
        become responsible for the security of all other packages that depend
        on that package.
    * Packages will be larger.

    Plan:
    * Create a temporary working dir.
    * Create virtualenv with `--system-site-packages`
      * Allows certain python libraries to be supplied by the operating system.
    * Install flocker from wheel file (which will include all the
      dependencies).
      * We'll need to keep track of which of our dependencies are provided on
        each platform and somehow omit those for from the build for that
        platform.
    * Generate an RPM version number.
    * Run `fpm` supplying the virtualenv path and version number.


    Followup Issues:
    * Update all pinned dependencies to instead be minimum dependencies.
      * This means that as and when sufficiently new versions of our
        dependencies are introduced upstream, we can remove them from our sumo
        build.
      * Those dependencies which are either too old or which are not packaged
        will be imported from the sumo virtualenv in preference.
      * Eventually we hope that all our dependencies will filter upstream and
        we will no longer have to bundle them; at which point the `flocker`
        package itself may be ready to be packaged by upstream distributions.

    Ticket refs:
         * https://github.com/ClusterHQ/flocker/issues/88

    Issue: CI integration (??):
    Update buildbot to build RPMs using new build scripts
    * Issue: create deb, mac, gentoo build slave
    * Issue: install from resulting package from repo and run test suite

    Issue: Client package build (??):
    Sumo packaging of flocker-deploy
    * For deb, RPM, and mac (via homebrew or ...)
    * Proper mac packages. See
      http://stackoverflow.com/questions/11487596/making-os-x-installer-packages-like-a-pro-xcode4-developer-id-mountain-lion-re

    Client package CI integration

    Misc:
    * separate stable and testing repos for deb and rpm
    * update python-flocker.spec.in requirements (remove most of them)
    * maybe even remove the spec file template and generate_spec function
      entirely (do we need it?)
    * do we still need to build an SRPM?
    * automatically build a wheel
    * automatically build an sdist
    """
    if target_dir is None:
        target_dir = FilePath(mkdtemp())
    return BuildSequence(
        steps=(
            InstallVirtualEnv(target_path=target_dir),
            InstallApplication(virtualenv_path=target_dir,
                               package_uri=package_uri),
            BuildRpm(
                destination_path=destination_path,
                source_path=target_dir,
                name='Flocker',
                prefix=FilePath('/opt/flocker'),
                epoch=b'0',
                rpm_version=make_rpm_version(version),
                license='ASL 2.0',
                url='https://clusterhq.com',
                vendor='ClusterHQ',
                maintainer='noreply@build.clusterhq.com',
                architecture=None,
                description='A Docker orchestration and volume management tool',
            )
        )
    )

from textwrap import dedent
class BuildOptions(usage.Options):
    """
    Command line options for the ``build-package`` tool.
    """
    synopsis = 'build-rpm [options] <package-uri>'

    optParameters = [
        ['destination-path', 'd', '.',
         'The path to a directory in which to create package files and '
         'artifacts.'],
    ]

    longdesc = dedent("""\
    Arguments:

    <package-uri>: The Python package url or path to install using ``pip``.
    """)

    def parseArgs(self, package_uri):
        """
        The Python package to install.
        """
        self['package-uri'] = package_uri

    def postOptions(self):
        """
        Coerce to ``FilePath`` where appropriate.
        """
        self['destination-path'] = FilePath(self['destination-path'])


class BuildScript(object):
    build_command = staticmethod(sumo_rpm_builder)

    def __init__(self, sys_module=None):
        """
        """
        if sys_module is None:
            sys_module = sys
        self.sys_module = sys_module

    def main(self, top_level=None, base_path=None):
        """
        Build a package.

        :param list argv: The arguments passed to the script.
        """
        options = BuildOptions()

        try:
            options.parseOptions(self.sys_module.argv[1:])
        except usage.UsageError as e:
            self.sys_module.stderr.write("%s\n" % (options,))
            self.sys_module.stderr.write("%s\n" % (e,))
            raise SystemExit(1)

        self.build_command(
            destination_path=options['destination-path'],
            package_uri=options['package-uri'],
            version=flocker.__version__,
        ).run()

main = BuildScript().main

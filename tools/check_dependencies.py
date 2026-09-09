"""Check installed requirement versions without contacting package indexes."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def missing_requirements(path):
    from pip._vendor.packaging.requirements import Requirement

    missing = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = version(requirement.name)
        except PackageNotFoundError:
            missing.append(line)
            continue
        if not requirement.specifier.contains(installed, prereleases=True):
            missing.append(line)
    return missing


if __name__ == '__main__':
    try:
        missing = missing_requirements(Path(__file__).resolve().parents[1] / 'requirements.txt')
    except Exception as error:
        print(f'Dependency check failed: {type(error).__name__}')
        raise SystemExit(1)
    print('\n'.join(missing) if missing else 'Dependencies satisfied.')
    raise SystemExit(bool(missing))

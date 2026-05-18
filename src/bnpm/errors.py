class BnpmError(Exception):
    pass


class ManifestError(BnpmError):
    pass


class SourceError(BnpmError):
    pass


class FetchError(BnpmError):
    pass

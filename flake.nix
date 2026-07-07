{
  description = "bnpm development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
  };

  outputs = { nixpkgs, ... }:
    let
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-darwin"
        "x86_64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      mkPkgs = system: import nixpkgs { inherit system; };
      devPackages = pkgs: [
        pkgs.python310
        pkgs.ruff
        pkgs.uv
      ];
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = mkPkgs system;
        in
        {
          default = pkgs.mkShell {
            packages = devPackages pkgs;

            shellHook = ''
              export UV_PYTHON_DOWNLOADS=never
            '';
          };
        });

      checks = forAllSystems (system:
        let
          pkgs = mkPkgs system;
        in
        {
          ci = pkgs.stdenv.mkDerivation {
            name = "bnpm-ci";
            src = ./.;
            nativeBuildInputs = devPackages pkgs;

            buildPhase = ''
              runHook preBuild

              export HOME="$TMPDIR/home"
              export UV_PYTHON_DOWNLOADS=never
              mkdir -p "$HOME"

              uv sync --frozen --all-groups
              ruff format --check .
              ruff check .
              uv run --frozen --all-groups python -m pytest
              uv build

              runHook postBuild
            '';

            installPhase = ''
              mkdir -p "$out"
              touch "$out/success"
            '';
          };
        });
    };
}

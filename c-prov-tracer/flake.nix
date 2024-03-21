{
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system}; in
      {
        devShells = {
          default = pkgs.mkShell {
            buildInputs = [
              (pkgs.python312.withPackages (pypkgs: [pypkgs.pycparser]))
              pkgs.gcc
            ];
          };
        };
      }
    );
}

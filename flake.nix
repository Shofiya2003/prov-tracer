{
  inputs = {
    nixpkgs = {
      url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    };
    flake-utils = {
      url = "github:numtide/flake-utils";
    };

    crane = {
      url = "github:ipetkov/crane";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    advisory-db = {
      url = "github:rustsec/advisory-db";
      flake = false;
    };

    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    crane,
    flake-utils,
    advisory-db,
    rust-overlay,
    ...
  }@inputs: let
    supported-systems = [
      "x86_64-linux"
      "i686-linux"
      "aarch64-linux"
      "armv7l-linux"
    ];
  in
    flake-utils.lib.eachSystem supported-systems (system: let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [(import rust-overlay)];
      };
      inherit (pkgs) lib;
      python312-debug = pkgs.python312.overrideAttrs (oldAttrs: {
        configureFlags = oldAttrs.configureFlags ++ ["--with-pydebug"];
        # patches = oldAttrs.patches ++ [ ./python.patch ];
      });
      export-and-rename = pkg: file-pairs:
        pkgs.stdenv.mkDerivation {
          pname = "${pkg.pname}-only-bin";
          dontUnpack = true;
          version = pkg.version;
          buildInputs = [ pkg ];
          buildPhase =
               "\n"
               (builtins.map
                 (pairs: "install -D ${pkg}/${builtins.elemAt pairs 0} $out/${builtins.elemAt pairs 1}")
                 file-pairs);
        };
      rust-stuff = (import ./probe_src/probe_frontend/rust-stuff.nix) ({ inherit system pkgs; } // inputs);
       in {
        packages = rec {
          python-dbg = python312-debug;
          libprobe-interface = pkgs.stdenv.mkDerivation {
           pname = "libprobe-interface";
            version = "0.1.0";
            src = ./probe_src/libprobe-interface;
            dontBuild = true;
            installPhase = ''
              install -D --target-directory $out/include/libprobe *.h
            '';
          };
          arena = pkgs.stdenv.mkDerivation {
            pname = "arena";
            version = "0.1.0";
            src = ./probe_src/arena;
            dontBuild = true;
            installPhase = ''
              install -D --target-directory $out/include/arena *.h
            '';
          };
          libprobe = pkgs.stdenv.mkDerivation rec {
            pname = "libprobe";
            version = "0.1.0";
            src = ./probe_src/libprobe;
            makeFlags = [ "INSTALL_PREFIX=$(out)" "SOURCE_VERSION=${version}" ];
            buildInputs = [
              libprobe-interface
              arena
              (pkgs.python312.withPackages (pypkgs: [
                pypkgs.pycparser
              ]))
            ];
          };
          probe-bundled = pkgs.stdenv.mkDerivation rec {
            pname = "probe-bundled";
            version = "0.1.0";
            dontUnpack = true;
            dontBuild = true;
            nativeBuildInputs = [ pkgs.makeWrapper ];
            installPhase = ''
              mkdir $out $out/bin
              makeWrapper \
                ${self.packages.${system}.probe-cli}/bin/probe \
                $out/bin/PROBE \
                --set __PROBE_LIB ${self.packages.${system}.libprobe}/lib
            '';
          };
        } // rust-stuff.packages;
        checks = self.packages.${system} // rust-stuff.checks;
        devShells = {
          default = pkgs.mkShell {
            buildInputs =
              [
                (pkgs.python312.withPackages (pypkgs: [
                  pypkgs.psutil
                  pypkgs.typer
                  pypkgs.pycparser
                  pypkgs.pytest
                  pypkgs.mypy
                  pypkgs.pygraphviz
                  pypkgs.networkx
                  pypkgs.ipython
                  pypkgs.pydot
                  pypkgs.rich
                ]))
                # (export-and-rename python312-debug [["bin/python" "bin/python-dbg"]])
                pkgs.which
                pkgs.gnumake
                pkgs.gcc
                pkgs.coreutils
                pkgs.bash
                pkgs.alejandra
                pkgs.hyperfine
                pkgs.just
                pkgs.black
                pkgs.ruff
              ]
              ++ (
                # gdb broken on apple silicon
                if system != "aarch64-darwin"
                then [pkgs.gdb]
                else []
              )
              ++ (
                # while xdot isn't marked as linux only, it has a dependency (xvfb-run) that is
                if builtins.elem system lib.platforms.linux
                then [pkgs.xdot]
                else []
              );
          };
        };
      }
    );
}

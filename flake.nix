
{
  description = "My dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    weathr.url = "github:Veirt/weathr";
  };

  outputs = { self, nixpkgs, flake-utils, weathr }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
      in {
        devShells.default = import ./shell.nix {
          inherit pkgs self system;
          weathr = weathr.packages.${system}.default;
        };

        formatter = pkgs.nixfmt-rfc-style;
      }
    );
}

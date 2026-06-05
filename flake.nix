{
  description = "flake for github:lavafroth/hum";

  outputs =
    {
      nixpkgs,
      ...
    }:
    let
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # timidity
            (pkgs.python3.withPackages (ps: with ps; [
              sounddevice
              numpy
              librosa
              mido
              scipy
              # matplotlib
              # ipython
              # soundcard
              # (ps.buildPythonPackage rec {
              #   pname = "kitcat";
              #   version = "1.2.1";
              #   format = "pyproject";
              #   src = pkgs.fetchPypi {
              #     inherit pname version;
              #     hash = "sha256-biNvOgAtSUUxvDtBH78Z6MG/pq9rhles3DDvokbpLsg=";
              #   };
              #   nativeBuildInputs = with ps; [ hatchling ];
              #   buildInputs = with ps; [
              #     matplotlib
              #     setuptools
              #   ];
              # })
            ]))
          ];

        };
        LD_LIBRARY_PATH = "${pkgs.portaudio}/lib:$LD_LIBRARY_PATH";
      });
    };
}

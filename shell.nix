{ pkgs, self, system, weathr }:

let
  shellConfig = {
    rcContent = ''
      eval "$(starship init zsh)"
      source ${pkgs.fzf}/share/fzf/key-bindings.zsh
      source ${pkgs.fzf}/share/fzf/completion.zsh

      alias ls='eza --icons --group-directories-first'
      alias ll='eza -l --icons --group-directories-first'
      alias la='eza -la --icons --group-directories-first'
      alias tree='eza --tree --icons'
      alias cat='bat --paging=never'
    '';
  };

in pkgs.mkShellNoCC {
  packages = with pkgs; [
    # Dev tools
    git
    gh
    flyctl
    jq
    yq

    # Shell enhancements
    zsh
    starship
    gum
    fastfetch
    neovim

    # Fun stuff
    cowsay
    lolcat
    weathr          # passed in from flake
    asciiquarium

    # Python
    python313
    uv
    basedpyright
    pipx

    # Node
    nodejs_22
    pnpm

    # CLI improvements
    eza
    bat
    fzf
    figlet
    glow
    fortune
    ponysay

    # Formatter from flake
    self.formatter.${system}
  ] ++ [
    # Native libs (for Python wheels, etc.)
    stdenv.cc.cc.lib
    openssl
    protobuf
    zlib
    blas
    lapack
    icu
    expat
    libffi
    curl
    xz
  ];

  env = {
    UV_PYTHON_PREFERENCE = "only-system";

    LD_LIBRARY_PATH = pkgs.lib.optionalString pkgs.stdenv.isLinux
      (pkgs.lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.openssl
        pkgs.zlib
        pkgs.blas
        pkgs.lapack
        pkgs.icu
        pkgs.expat
        pkgs.libffi
        pkgs.curl
        pkgs.xz
      ]);

    NIX_LD = pkgs.lib.optionalString pkgs.stdenv.isLinux
      (builtins.readFile "${pkgs.stdenv.cc}/nix-support/dynamic-linker");
  };

  shellHook = ''
    ZDOTDIR=$(mktemp -d)
    cat > "$ZDOTDIR/.zshrc" << 'ZSHRC'
${shellConfig.rcContent}
ZSHRC
    export ZDOTDIR
    starship preset -o "$ZDOTDIR/starship.toml" jetpack
    export STARSHIP_CONFIG="$ZDOTDIR/starship.toml"
    exec ${pkgs.zsh}/bin/zsh
  '';
}

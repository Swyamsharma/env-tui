# Maintainer: Swyam Sharma swyamsharma13102003@gmail.com

pkgname=env-tui
pkgver=0.1.0
pkgrel=1
pkgdesc="A Textual TUI for managing environment variables"
arch=('any')
url="https://github.com/Swyamsharma/env-tui" # TODO: Replace with your actual project URL
license=('MIT')
depends=('python' 'python-textual' 'python-pyperclip')
optdepends=('xclip: for clipboard support'
            'xsel: for clipboard support')
# Since we are building from the current directory, list the source files.
# makepkg will look for these in the same directory as the PKGBUILD.
source=('env_tui.py'
        'ui.py'
        'shell_utils.py'
        'config.py'
        'env_tui.css'
        'LICENSE'
        'README.md')
# Generate checksums using 'updpkgsums' command after downloading/placing sources
sha256sums=('3f88a674cf8ce202314b80cde61aa055ce9b69ab6fdc8e51e77bc79be1863512'
            '15dfc8bffb103ecc87000f27b5f3992edbc0888b2b59953d0800d571808bf1e3'
            '88fcf8b22a0da4a0c9efed2ae4ef4159ce12a8762ed751af3718c6f6236fbb3b'
            '8738eef7d2905fa303a6d39c7b25c89c196ccb6e42c66ea2dbe9869741195278'
            'bb52ac2c467642f21330a5ef063b1f8284e8505560f9d860f048e3dc7d7583ed'
            'd505aaff06638ae4fe9fdf76fa967a14da379443ac984ad477bfc8c113f61ec1'
            'eaa2b574cb8e30a443297b0a7897c9842c17f8a1f53c7e7f48f39fdfb7e7236f')

package() {
  cd "$srcdir"

  # Install application files
  install -Dm644 env_tui.py "$pkgdir/usr/share/$pkgname/env_tui.py"
  install -Dm644 ui.py "$pkgdir/usr/share/$pkgname/ui.py"
  install -Dm644 shell_utils.py "$pkgdir/usr/share/$pkgname/shell_utils.py"
  install -Dm644 config.py "$pkgdir/usr/share/$pkgname/config.py"
  install -Dm644 env_tui.css "$pkgdir/usr/share/$pkgname/env_tui.css"

  # Install executable wrapper
  install -Dm755 /dev/stdin "$pkgdir/usr/bin/$pkgname" << EOF
#!/bin/bash
# Wrapper script for env-tui
python /usr/share/$pkgname/env_tui.py "\$@"
EOF

  # Install license
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

  # Install documentation (optional)
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}

# vim:set ts=2 sw=2 et:

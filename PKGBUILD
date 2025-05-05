# Maintainer: Swyam Sharma <swyamsharma13102003@gmail.com>

# Package metadata
pkgname=env-tui
_pkgname=env-tui
pkgver=0.1.0
pkgrel=1
pkgdesc="A Textual TUI for managing environment variables"
arch=('any')
url="https://github.com/Swyamsharma/env-tui"
license=('MIT')

depends=(
    'python'
)

makedepends=(
    'python-build'     
    'python-installer' 
    'python-wheel'   
)

optdepends=(
    'xclip: for clipboard support (X11)'
    'wl-clipboard: for clipboard support (Wayland)'
    'xsel: for clipboard support (X11 alternate)'
)

source=("$pkgname-$pkgver.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")

sha256sums=('c9826c51110fc05da530d4db7816566cfe2139bea200b7f792ce85622b62bf54')

build() {
  cd "$srcdir/${_pkgname}-${pkgver}"
  python -m build --wheel --no-isolation
}

package() {
  cd "$srcdir/${_pkgname}-${pkgver}"
  python -m installer --destdir="$pkgdir" dist/*.whl

  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}


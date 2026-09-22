"""
Lythos Kinematic sürümünü PyPI'ya yükler — Thonny gibi bir düzenleyiciden de
çalışır: yeşil Çalıştır düğmesine basıp kabuktaki sorulara yanıt vermek yeterli.

Terminalde `python -m build && twine upload dist/*` ne yapıyorsa aynısını yapar;
farkı, çalışmak için kendi sanal ortamını kurmasıdır. Böylece sistem Python'una
hiçbir şey kurulmaz — pip'in sistem paketlerine dokunmayı reddettiği dağıtımlarda
(Arch, yeni Debian/Ubuntu) çalışan ile çalışmayan arasındaki fark budur.

Sırayla yaptıkları:

    1. ~/.lythos-release içinde küçük bir ortam kurar, içine build ve twine koyar
    2. isterseniz dağıtımı yeniden derler (dist/ temizlenir)
    3. pyproject.toml'daki sürüm ile dosyaların sürümünü karşılaştırır
    4. bu sürümün PyPI'da zaten yayımlanmış olup olmadığına bakar
    5. `twine check` ile dosyaları denetler
    6. ~/.pypirc'te token yoksa sorar (girdiğiniz token ekrana yazılmaz)
    7. ne yükleyeceğini gösterir, onayınızı ister, sonra yükler

5. adıma kadar hiçbir şey hiçbir yere gönderilmez ve "evet" dışında bir yanıt
işlemi durdurur.

PyPI bir sürüm numarasını bir kez kabul eder, bir daha asla. 3. ve 4. adımın
yazdıklarını onaylamadan önce okuyun.

Token bu betikte saklanmaz, yazdırılmaz ve günlüğe geçmez; yalnızca twine'a
ortam değişkeni olarak geçirilir.
"""

import configparser
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import venv

# Gerçek PyPI yerine TestPyPI'da prova yapmak için True yapın. TestPyPI, kendi
# hesapları ve kendi token'ları olan tek kullanımlık bir kopyadır; oraya
# yüklediğiniz hiçbir şey kalıcı değildir.
TEST_PYPI = False

PROJECT = "lythoskinematic"
ENV = os.path.expanduser("~/.lythos-release")
PYPIRC = os.path.expanduser("~/.pypirc")
REPOSITORY = "testpypi" if TEST_PYPI else "pypi"
SITE = "https://test.pypi.org" if TEST_PYPI else "https://pypi.org"
TOKEN_PAGE = f"{SITE}/manage/account/token/"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DIST = os.path.join(ROOT, "dist")

# Dağıtım dosyası adından paket adı ve sürüm.
FILENAME = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+?)-(?P<version>\d[^-]*?)"
                      r"(?:-py3-none-any)?\.(?:whl|tar\.gz)$")


# --------------------------------------------------------------------- sorular
def ask(question, default=None):
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return answer or (default or "")


def yes(question, default="hayır"):
    return ask(f"{question} (evet/hayır)", default).lower() in ("e", "evet", "y", "yes")


def stop(message):
    raise SystemExit(f"\n{message}")


# ---------------------------------------------------------------------- ortam
def tool(name):
    """Kendi ortamımızdaki bir programın yolu."""
    binary = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return os.path.join(ENV, binary, name + suffix)


def run(command, failure, env=None, cwd=None):
    result = subprocess.run(command, env=env, cwd=cwd)
    if result.returncode != 0:
        stop(f"{failure} (çıkış kodu {result.returncode}).")
    return result


def prepare_environment(need_build):
    if not os.path.isfile(tool("python")):
        print(f"{ENV} içinde küçük bir ortam kuruluyor ...")
        venv.EnvBuilder(with_pip=True, clear=True).create(ENV)
    wanted = ["twine"] + (["build"] if need_build else [])
    missing = [name for name in wanted if not os.path.isfile(tool(name))]
    if missing:
        print(f"Ortama kuruluyor: {', '.join(missing)} ...")
        run([tool("python"), "-m", "pip", "install", "--quiet",
             "--disable-pip-version-check", "--upgrade", *missing],
            "Araçlar kurulamadı")
    print("Hazır.\n")


# ------------------------------------------------------------------ sürüm
def declared_version():
    """pyproject.toml'da yazan sürüm."""
    path = os.path.join(ROOT, "pyproject.toml")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def published_versions():
    """PyPI'da yayımlanmış sürümler. Ağ yoksa None döner (token gerekmez)."""
    url = f"{SITE}/pypi/{PROJECT}/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return set(json.load(response).get("releases", {}))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return set()                 # proje henüz yok: ilk yükleme
        return None
    except Exception:
        return None                      # ağ yok; yükleme yine de denenebilir


# ------------------------------------------------------------------ dosyalar
def releases_in(folder):
    """Bir klasördeki dağıtım dosyalarını sürüme göre gruplar."""
    found = {}
    if not os.path.isdir(folder):
        return found
    for entry in sorted(os.listdir(folder)):
        match = FILENAME.match(entry)
        if match:
            key = (match.group("name"), match.group("version"))
            found.setdefault(key, []).append(os.path.join(folder, entry))
    return found


def build_distribution():
    """dist/ klasörünü temizleyip yeniden derler."""
    if os.path.isdir(DIST):
        print(f"{DIST} temizleniyor ...")
        shutil.rmtree(DIST)
    print("Dağıtım derleniyor ...\n")
    run([tool("python"), "-m", "build"], "Derleme başarısız", cwd=ROOT)
    print()


def choose_files():
    found = releases_in(DIST)
    if not found:
        print(f"{DIST} içinde .whl veya .tar.gz yok.")
        if not yes("Şimdi derleyeyim mi?", "evet"):
            stop("Yüklenecek bir şey yok.")
        build_distribution()
        found = releases_in(DIST)
        if not found:
            stop("Derleme bir şey üretmedi.")

    keys = sorted(found)
    print(f"{DIST} içinde bulunanlar:")
    for index, (name, version) in enumerate(keys, start=1):
        files = ", ".join(os.path.basename(f) for f in found[(name, version)])
        print(f"  {index}. {name} {version} — {files}")

    if len(keys) == 1:
        key = keys[0]
    else:
        # Birden fazla sürüm var: yanlışını yüklemek geri alınamaz, asla tahmin etme.
        print("\nBurada birden fazla sürüm var.")
        while True:
            answer = ask("Hangi numara")
            if answer.isdigit() and 1 <= int(answer) <= len(keys):
                key = keys[int(answer) - 1]
                break
            print("Yukarıdaki numaralardan birini yazın.")

    files = found[key]
    if not any(f.endswith(".whl") for f in files):
        print("\nUyarı: .whl yok, yalnızca kaynak arşivi var.")
    if not any(f.endswith(".tar.gz") for f in files):
        print("\nUyarı: .tar.gz kaynak arşivi yok, yalnızca tekerlek var.")
    return key, files


def check_version(name, version):
    """Sürümü pyproject.toml ve PyPI ile karşılaştırır."""
    declared = declared_version()
    if declared and declared != version:
        print(f"\nUyarı: pyproject.toml {declared} diyor, dosyalar {version}.")
        print("Muhtemelen sürümü yükselttikten sonra yeniden derlemediniz.")
        if not yes("Yine de devam edilsin mi?"):
            stop("Durduruldu.")

    published = published_versions()
    if published is None:
        print("\nPyPI'ya bakılamadı (ağ yok); sürüm kontrolü atlandı.")
        return
    if version in published:
        stop(f"{name} {version} PyPI'da zaten var. Bir sürüm numarası bir kez "
             f"kabul edilir: pyproject.toml'da sürümü yükseltip yeniden derleyin.")
    if not published:
        print(f"\n{name} PyPI'da henüz yok; bu ilk yükleme olacak.")
        print("İlk yükleme için token'ın kapsamı 'Entire account' olmalıdır —")
        print("proje kapsamlı token ancak var olan bir proje için üretilebilir.")
    else:
        newest = sorted(published)[-1]
        print(f"\nPyPI'daki mevcut sürümler: {len(published)} adet (son: {newest}).")


# ------------------------------------------------------------------- token
def stored_token():
    """~/.pypirc'te bu depo için bir token varsa onu döndürür."""
    if not os.path.isfile(PYPIRC):
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(PYPIRC)
    except configparser.Error:
        return None
    if parser.has_option(REPOSITORY, "password"):
        return parser.get(REPOSITORY, "password")
    return None


def get_token():
    """Token'ı bulur ya da sorar. Döndürür: (token, yeni mi)."""
    token = stored_token()
    if token:
        print(f"{PYPIRC} içindeki token kullanılıyor.\n")
        return token, False

    print(f"Bir API token gerekiyor. {TOKEN_PAGE} adresinden alınır.")
    print("  · 'pypi-' ile başlar ve yalnızca bir kez gösterilir")
    print("  · bir projenin ilk yüklemesi için kapsam 'Entire account' olmalı")
    print("  · proje yayımlandıktan sonra projeye özel bir token ile değiştirin\n")
    try:
        token = getpass.getpass("Token (yazdıklarınız görünmez): ").strip()
    except Exception:
        # Bazı düzenleyicilerin kabuğunda gizli giriş yoktur.
        print("(Bu kabukta gizli giriş yok — yazdığınız token görünecek.)")
        token = ask("Token")
    if not token:
        stop("Token yok, yükleme yok.")
    if not token.startswith("pypi-"):
        print("\nBu bir token'a benzemiyor — token'lar 'pypi-' ile başlar.")
        if not yes("Yine de kullanılsın mı?"):
            stop("Durduruldu.")
    return token, True


def offer_to_save(token):
    print(f"\nToken {PYPIRC} içinde tutulabilir, bir daha sorulmaz.")
    print("Bu bir paroladır: dosya yalnızca sizin okuyabileceğiniz şekilde yazılır.")
    if not yes("Kaydedilsin mi?"):
        return
    parser = configparser.ConfigParser(interpolation=None)
    if os.path.isfile(PYPIRC):
        parser.read(PYPIRC)
    if not parser.has_section(REPOSITORY):
        parser.add_section(REPOSITORY)
    parser.set(REPOSITORY, "username", "__token__")
    parser.set(REPOSITORY, "password", token)
    # Doğru izinlerle baştan oluştur; önce token'ı yazıp sonra daraltma.
    handle = os.open(PYPIRC, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        parser.write(fh)
    os.chmod(PYPIRC, 0o600)
    print(f"{PYPIRC} dosyasına kaydedildi.")


def explain_failure(name):
    """Yükleme başarısızsa en olası nedenleri anlatır."""
    print("\n" + "-" * 62)
    print("Yükleme reddedildi. En sık görülen nedenler:")
    print()
    print("  403 Forbidden — token kapsamı yanlış olabilir. Başka bir projeye")
    print(f"     (örneğin lythosfea) özel bir token {name} için çalışmaz.")
    print("     İlk yükleme için 'Entire account' kapsamlı bir token üretin:")
    print(f"     {TOKEN_PAGE}")
    print("     Token süresiz geçerlidir; iptal edilmedikçe eskimez.")
    print()
    print("  400 File already exists — bu sürüm zaten yayımlanmış. Sürümü")
    print("     pyproject.toml'da yükseltip yeniden derleyin.")
    print()
    print(f"  Kayıtlı token {PYPIRC} içindedir; yanlışsa oradan silin,")
    print("     betik yeniden soracaktır.")
    print("-" * 62)


# -------------------------------------------------------------------- ana akış
def main():
    where = ("TestPyPI (prova — oraya yüklenen hiçbir şey kalıcı değildir)"
             if TEST_PYPI else "PyPI (gerçek olan)")
    print(f"Hedef: {where}\n")

    rebuild = yes("Dağıtım yeniden derlensin mi?", "evet")
    prepare_environment(need_build=rebuild)
    if rebuild:
        build_distribution()

    (name, version), files = choose_files()
    check_version(name, version)

    print("\nDosyalar denetleniyor ...")
    run([tool("twine"), "check", *files], "Dosyalar denetimden geçemedi")

    print("\n" + "-" * 62)
    print(f"Yüklenmek üzere: {name} {version}")
    for path in files:
        print(f"    {os.path.basename(path)}  "
              f"({os.path.getsize(path) / 1024:.0f} kB)")
    print(f"  hedef: {where}")
    print("\nBir sürüm numarası bir kez kabul edilir, bir daha asla. Yanlış bir")
    print("şey varsa burada durun, düzeltin, sürümü yükseltin ve yeniden derleyin.")
    print("-" * 62 + "\n")
    if not yes("Şimdi yüklensin mi?"):
        stop("Durduruldu. Hiçbir şey gönderilmedi.")

    token, is_new = get_token()

    environment = dict(os.environ)
    environment["TWINE_USERNAME"] = "__token__"
    environment["TWINE_PASSWORD"] = token
    environment["TWINE_NON_INTERACTIVE"] = "1"
    if TEST_PYPI:
        environment["TWINE_REPOSITORY"] = "testpypi"

    print("\nYükleniyor ...\n")
    result = subprocess.run([tool("twine"), "upload", *files], env=environment)
    if result.returncode != 0:
        explain_failure(name)
        stop(f"Yükleme başarısız (çıkış kodu {result.returncode}).")

    print(f"\nBitti. {SITE}/project/{name}/{version}/")
    print(f"Artık herkes şunu çalıştırabilir:  pip install {name}")
    print("\nDoğrulamak için boş bir ortamda:")
    print(f"    python -m venv /tmp/kontrol")
    print(f"    /tmp/kontrol/bin/pip install {name}")
    print(f"    /tmp/kontrol/bin/lythos-kinematic --version")

    if is_new:
        offer_to_save(token)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as reason:
        print(reason)
    except KeyboardInterrupt:
        print("\nDurduruldu.")

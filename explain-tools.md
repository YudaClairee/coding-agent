# Explain `commands.py` dan `file_system.py`

Dokumen ini dibuat buat bantu kamu ngerti dua file ini:

- `app/agents/tools/commands.py`
- `app/agents/tools/file_system.py`

Fokusnya ada 2:

1. penjelasan baris per baris dengan bahasa yang lebih santai
2. rewrite versi lebih beginner-friendly supaya pola pikir kodenya kebaca

---

## Gambaran Besar Dulu

Dua file ini bukan script Python biasa yang langsung dijalankan dari atas ke bawah.

Mereka lebih mirip **definisi capability** buat agent:

- `commands.py` = kasih agent kemampuan buat jalanin command terminal
- `file_system.py` = kasih agent kemampuan buat baca/tulis/edit file

Mereka pakai `Toolkit` dari `agno.tools`.

Artinya, framework `agno` kemungkinan punya konsep seperti:

- kamu bikin class tool
- kamu daftar method mana yang boleh dipakai agent
- nanti agent bisa manggil method itu sebagai "tool"

Jadi kalau syntax-nya terasa asing, itu wajar. Ini campuran dari:

- Python modern
- OOP / class inheritance
- pola framework agent

---

## Cheat Sheet Syntax Yang Terasa Asing

Sebelum masuk baris per baris, ini terjemahan cepat syntax yang biasanya bikin bingung:

- `class X(Toolkit)`  
  Artinya class `X` mewarisi fitur dari `Toolkit`.

- `super().__init__(...)`  
  Artinya panggil constructor milik parent class.

- `str | None`  
  Artinya nilainya bisa `str` atau `None`.

- `list[str]`  
  Artinya list yang isinya string.

- `self.sesuatu`  
  Artinya atribut atau method milik object itu sendiri.

- `tools=[self.read_file, self.write_file]`  
  Artinya method-method itu didaftarkan ke framework sebagai tool yang bisa dipakai.

- `-> str`  
  Artinya function ini diharapkan mengembalikan string.

---

## Penjelasan `commands.py`

### Tujuan file

File ini bikin tool untuk menjalankan perintah terminal, tapi tetap dibungkus dengan:

- validasi policy
- timeout
- pembatas output
- error handling

Jadi ini bukan sekadar `subprocess.run(...)`, tapi ada lapisan pengaman di atasnya.

---

### Bedah per bagian

#### Import

```python
import logging
import shlex
import subprocess

from agno.tools import Toolkit

from app.agents.tools.policy import CommandPolicy, PolicyMode
```

Arti masing-masing:

- `logging` buat nulis log
- `shlex` buat quote / parse command dengan aman
- `subprocess` buat jalanin command sistem
- `Toolkit` adalah base class dari framework agent
- `CommandPolicy` dan `PolicyMode` dipakai buat ngecek command boleh jalan atau tidak

---

#### Logger

```python
logger = logging.getLogger(__name__)
```

Ini bikin logger untuk file ini.

`__name__` biasanya nama module Python saat file ini di-import.

Jadi nanti log dari file ini bisa dibedakan dari file lain.

---

#### Class utama

```python
class CommandTools(Toolkit):
    """Tools for executing shell commands."""
```

Ini artinya:

- bikin class bernama `CommandTools`
- class ini turunan dari `Toolkit`
- jadi class ini bukan class bebas, tapi mengikuti kontrak / pola yang diharapkan framework

Kalau dibahas santai:  
"Saya bikin kumpulan tool command, dan saya numpang fondasi dari `Toolkit`."

---

#### Constructor / `__init__`

```python
def __init__(
    self,
    project_path: str | None = None,
    timeout: int = 30,
    max_output_length: int = 10000,
    policy_mode: PolicyMode = PolicyMode.GUARDED,
):
```

Ini parameter saat object dibuat:

- `project_path`: folder kerja command, bisa string atau `None`
- `timeout`: maksimal berapa detik command boleh jalan
- `max_output_length`: output maksimal yang akan dikembalikan
- `policy_mode`: mode keamanan command

Kenapa `str | None`?  
Karena kadang path-nya diset, kadang tidak.

---

```python
self.project_path = project_path
self.timeout = timeout
self.max_output_length = max_output_length
self.policy = CommandPolicy(mode=policy_mode)
```

Ini nyimpen nilai ke object.

Yang penting:

- `self.project_path` dipakai jadi `cwd`
- `self.timeout` dipakai buat timeout subprocess
- `self.max_output_length` dipakai buat truncate output
- `self.policy` bikin object policy untuk validasi command

---

```python
super().__init__(name="commands", tools=[self.run_command, self.exec_command])
```

Ini bagian paling framework-ish.

Artinya:

- panggil constructor `Toolkit`
- kasih nama toolkit ini: `"commands"`
- daftar tool yang tersedia:
  - `run_command`
  - `exec_command`

Jadi framework nanti tahu:

"Toolkit bernama `commands` punya 2 kemampuan ini."

---

### `run_command`

```python
def run_command(self, program: str, args: list[str] | None = None) -> str:
```

Method ini cara **lebih aman** untuk jalanin command.

Contoh mental model:

- `program = "ls"`
- `args = ["-la"]`

jadi bukan raw string `"ls -la"`, tapi dipisah per bagian.

Kenapa ini lebih aman?  
Karena tidak lewat shell parsing.

---

```python
args = args or []
full_command = [program] + args
command_str = " ".join(shlex.quote(arg) for arg in full_command)
```

Artinya:

- kalau `args` kosong / `None`, ubah jadi list kosong
- gabungkan program dan args jadi satu list
- bikin versi string-nya untuk logging / policy check

Misalnya:

- `program = "git"`
- `args = ["status"]`

hasil `full_command`:

```python
["git", "status"]
```

hasil `command_str`:

```python
"git status"
```

---

```python
logger.info(f"Executing run_command: {command_str} (cwd: {self.project_path})")
```

Ini cuma nulis log bahwa command akan dijalankan.

---

```python
is_allowed, error_msg, requires_conf = self.policy.validate(command_str)
```

Ini validasi command terhadap policy.

Return value-nya tuple 3 isi:

- `is_allowed`: boleh atau tidak
- `error_msg`: alasan kalau gagal
- `requires_conf`: perlu konfirmasi user atau tidak

Karena Python bisa unpack tuple, maka hasil 3 nilai itu langsung dimasukkan ke 3 variabel.

---

```python
if not is_allowed:
    logger.warning(f"Command blocked by policy: {command_str}. Reason: {error_msg}")
    return f"Error: {error_msg}"
```

Kalau command diblok:

- tulis warning
- langsung balikin error string

Jadi function ini **tidak raise exception** di sini, tapi return string error.

Ini desain yang lumayan umum di tool agent, karena hasil tool sering lebih enak dikembalikan sebagai text.

---

```python
if requires_conf:
    logger.warning(f"Command requires confirmation: {command_str}")
    return f"Error: Command '{command_str}' requires manual user confirmation. This agent is not authorized to run it automatically."
```

Kalau command technically boleh, tapi butuh konfirmasi:

- tetap tidak dieksekusi
- dikembalikan sebagai pesan error/penolakan

Contohnya di `policy.py`, `git push` termasuk yang perlu konfirmasi.

---

```python
result = subprocess.run(
    full_command,
    shell=False,
    capture_output=True,
    text=True,
    timeout=self.timeout,
    cwd=self.project_path,
)
```

Ini inti eksekusi command.

Arti argumennya:

- `full_command`: list command dan arg
- `shell=False`: tidak pakai shell, lebih aman
- `capture_output=True`: stdout/stderr ditangkap
- `text=True`: hasil output berupa string, bukan bytes
- `timeout=self.timeout`: hentikan kalau terlalu lama
- `cwd=self.project_path`: jalankan di folder tertentu

`shell=False` penting banget.  
Ini alasan `run_command` jadi jalur yang lebih aman.

---

```python
return self._format_result(result)
```

Setelah command selesai, hasilnya dirapikan oleh helper method `_format_result`.

---

```python
except subprocess.TimeoutExpired as e:
    return self._handle_timeout(e, command_str)
except Exception as e:
    return self._handle_error(e, command_str)
```

Kalau timeout, masuk handler timeout.  
Kalau error umum lain, masuk handler error.

Jadi function utamanya tetap bersih.

---

### `exec_command`

```python
def exec_command(self, command: str) -> str:
```

Ini versi raw shell command.

Dipakai kalau butuh hal yang tidak enak diekspresikan sebagai `program + args`, misalnya:

- pipe `|`
- redirect `>`
- chaining shell tertentu

Contoh:

```bash
ls -la | grep py
```

Ini lebih cocok lewat `exec_command`.

---

Validasi policy-nya hampir sama seperti `run_command`.

Bedanya di bagian ini:

```python
result = subprocess.run(
    command,
    shell=True,
    capture_output=True,
    text=True,
    timeout=self.timeout,
    cwd=self.project_path,
)
```

Yang beda paling penting:

- input-nya string utuh
- `shell=True`

`shell=True` bikin shell ikut parsing string command, jadi lebih fleksibel, tapi juga lebih berisiko.

Makanya docstring-nya bilang:

"pakai `run_command` kalau bisa."

Itu keputusan desain yang bagus.

---

### `_format_result`

```python
def _format_result(self, result: subprocess.CompletedProcess) -> str:
```

Method helper buat ngerapihin hasil command.

---

```python
stdout = result.stdout or ""
stderr = result.stderr or ""
exit_code = result.returncode
```

Ambil data hasil subprocess.

- `stdout` = output normal
- `stderr` = output error
- `returncode` = exit code command

`or ""` dipakai supaya kalau `None`, langsung jadi string kosong.

---

```python
output_parts = []
if stdout:
    output_parts.append(stdout)
if stderr:
    output_parts.append(f"STDERR:\n{stderr}")
if exit_code != 0:
    output_parts.append(f"Exit code: {exit_code}")
```

Ini bikin output gabungan:

- kalau ada stdout, masuk
- kalau ada stderr, masuk juga dengan label
- kalau exit code bukan 0, tampilkan juga

Jadi hasil tool ini bukan object structured, tapi text yang enak dibaca.

---

```python
output = "\n".join(output_parts) or "(no output)"
```

Kalau semua kosong, hasil akhirnya jadi:

```text
(no output)
```

---

```python
if len(output) > self.max_output_length:
    trunc_msg = f"\n... (output truncated, total length: {len(output)} chars)"
    output = output[: self.max_output_length] + trunc_msg
```

Kalau output kepanjangan, dipotong.

Ini penting buat agent system supaya:

- context tidak meledak
- response tetap manageable

---

### `_handle_timeout`

Method ini bikin pesan error kalau command timeout.

Dia juga coba ambil partial stdout/stderr kalau ada.

Bagusnya:

- user tetap dapat petunjuk walau command gagal selesai

---

### `_handle_error`

Method ini fallback buat error umum lain.

Dia:

- nulis log error
- balikin string error ke caller

Jadi dari luar, tool ini tetap konsisten: output utamanya string.

---

## Ringkasan `commands.py`

Kalau disederhanakan:

1. terima command
2. validasi policy
3. jalankan command
4. tangkap output
5. format hasil
6. handle timeout/error

Secara desain, file ini sudah cukup rapi.

Yang mungkin bikin asing bukan logikanya, tapi karena dia ditulis dalam style:

- OOP
- framework tool registration
- Python modern type hint

---

## Penjelasan `file_system.py`

### Tujuan file

File ini bikin tool untuk operasi file sederhana:

- baca file
- tulis file
- edit file dengan replace string

Tool ini dibatasi ke `base_dir`, jadi tidak bebas akses seluruh filesystem.

Itu ide yang bagus.

---

### Bedah per bagian

#### Import

```python
import os

from agno.tools import Toolkit
```

`os` dipakai buat urusan path dan filesystem.  
`Toolkit` tetap base class framework.

---

#### Class utama

```python
class FileSystemTools(Toolkit):
    """Tools for reading, writing, and editing files."""
```

Sama seperti `commands.py`, ini mendefinisikan toolkit baru.

---

#### Constructor

```python
def __init__(self, base_dir: str | None = None):
    self.base_dir = base_dir or os.getcwd()
```

Kalau `base_dir` tidak dikasih, default-nya current working directory.

Jadi semua operasi file akan dianggap relatif ke folder itu.

---

```python
super().__init__(
    name="file_system",
    tools=[self.read_file, self.write_file, self.edit_file],
)
```

Ini daftar method yang dijadikan tool:

- `read_file`
- `write_file`
- `edit_file`

Nama toolkit-nya `"file_system"`.

---

### `_resolve`

```python
def _resolve(self, path: str) -> str:
    resolved = os.path.normpath(os.path.join(self.base_dir, path))
    if not resolved.startswith(self.base_dir):
        raise ValueError(f"Path {path} is outside the base directory")
    return resolved
```

Ini function paling penting di file ini.

Tujuannya:

- gabungkan `base_dir` dengan path relatif
- normalisasi path
- cegah akses keluar folder dasar

Contoh:

- `base_dir = "/project"`
- `path = "notes/a.txt"`

hasil:

```text
/project/notes/a.txt
```

Kalau ada yang coba:

```text
../../etc/passwd
```

setelah dinormalisasi, dia bisa keluar dari `/project`, dan itu ditolak.

---

### Kenapa `normpath` dan `join` dipakai?

- `os.path.join(...)` buat gabung path dengan benar
- `os.path.normpath(...)` buat merapikan path, misalnya menghilangkan `a/../b`

Ini umum banget di Python untuk urusan file path.

---

### `read_file`

```python
def read_file(self, path: str) -> str:
```

Function ini baca isi file dan balikin string.

---

```python
resolved = self._resolve(path)
with open(resolved) as f:
    return f.read()
```

Alurnya:

1. ubah path relatif jadi absolute path aman
2. buka file
3. baca semua isi file
4. return sebagai string

`with open(...)` dipakai supaya file otomatis ditutup setelah selesai.

---

### `write_file`

```python
def write_file(self, path: str, content: str) -> str:
```

Ini tulis isi ke file.

---

```python
resolved = self._resolve(path)
os.makedirs(os.path.dirname(resolved), exist_ok=True)
with open(resolved, "w") as f:
    f.write(content)
return f"Written to {path}"
```

Urutannya:

1. resolve path
2. bikin parent directory kalau belum ada
3. buka file mode `"w"` = write / overwrite
4. tulis content
5. balikin pesan sukses

`exist_ok=True` artinya:

- kalau folder sudah ada, tidak error

Ini enak karena caller tidak perlu mikir folder parent sudah dibuat atau belum.

---

### `edit_file`

```python
def edit_file(self, path: str, old_string: str, new_string: str) -> str:
```

Ini edit file dengan cara replace string tertentu.

Bukan parser pintar, bukan patch system, cuma string replacement biasa.

---

```python
resolved = self._resolve(path)
with open(resolved) as f:
    content = f.read()
```

Pertama baca dulu seluruh isi file.

---

```python
if old_string not in content:
    return f"Error: '{old_string}' not found in {path}"
```

Kalau target string tidak ada, jangan tulis apa-apa.

Itu bagus, karena mencegah edit diam-diam yang salah.

---

```python
content = content.replace(old_string, new_string, 1)
```

Ini bagian penting:

- replace `old_string` jadi `new_string`
- `1` artinya **hanya ganti 1 kemunculan pertama**

Kalau angka `1` tidak ada, semua kemunculan akan terganti.

Jadi penulis file ini sengaja bikin edit-nya lebih konservatif.

---

```python
with open(resolved, "w") as f:
    f.write(content)
return f"Edited {path}"
```

Setelah isi baru jadi:

- overwrite file
- balikin pesan sukses

---

## Ringkasan `file_system.py`

Kalau disederhanakan:

1. semua path dibatasi di `base_dir`
2. file bisa dibaca
3. file bisa ditulis
4. file bisa diedit dengan replace satu string

Ini file kecil, tapi idenya jelas:

"Kasih agent akses file, tapi tetap dibatasi area kerjanya."

---

## Apa Yang Sebenarnya Bikin Keduanya Terasa Aneh?

Bukan karena Python-nya aneh, tapi karena kamu lagi lihat beberapa hal sekaligus:

### 1. Python modern

Contoh:

- `str | None`
- `list[str]`

Kalau kamu biasa lihat Python lama, kamu mungkin lebih familiar dengan:

```python
from typing import Optional, List

path: Optional[str]
args: List[str]
```

Versi baru cuma lebih ringkas.

---

### 2. OOP

Ada:

- class
- inheritance
- `self`
- `super()`

Kalau kamu lebih sering nulis function biasa, ini bakal terasa lebih abstrak.

---

### 3. Framework pattern

File ini bukan cuma "logika", tapi juga "registrasi capability" ke framework.

Bagian seperti ini:

```python
super().__init__(name="commands", tools=[self.run_command, self.exec_command])
```

itu bukan Python aneh, tapi API dari framework `agno`.

Jadi kamu sedang baca kode yang:

- menjelaskan perilaku
- sekaligus ngomong ke framework

Makanya lebih terasa "meta".

---

## Rewrite Versi Beginner-Friendly

Di bawah ini aku bikin versi yang lebih plain.

Tujuannya bukan mengganti code asli, tapi supaya logikanya kebaca dulu tanpa beban framework.

---

## Rewrite sederhana untuk `commands.py`

```python
import subprocess


class SimpleCommandRunner:
    def __init__(self, project_path=None, timeout=30):
        self.project_path = project_path
        self.timeout = timeout

    def run_command(self, program, args=None):
        if args is None:
            args = []

        full_command = [program] + args

        try:
            result = subprocess.run(
                full_command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.project_path,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\nSTDERR:\n" + result.stderr
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"

            return output or "(no output)"

        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {self.timeout}s"
        except Exception as e:
            return f"Error: {e}"
```

### Kenapa versi ini lebih gampang dibaca?

Karena:

- tidak ada `Toolkit`
- tidak ada policy
- tidak ada helper method terpisah
- fokus cuma ke inti `subprocess.run`

Jadi pola pikirnya kelihatan:

1. susun command
2. jalankan
3. ambil output
4. handle error

---

## Rewrite sederhana untuk `file_system.py`

```python
import os


class SimpleFileTools:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.getcwd()

    def resolve_path(self, path):
        full_path = os.path.normpath(os.path.join(self.base_dir, path))

        if not full_path.startswith(self.base_dir):
            raise ValueError("Path keluar dari base_dir")

        return full_path

    def read_file(self, path):
        full_path = self.resolve_path(path)
        with open(full_path) as f:
            return f.read()

    def write_file(self, path, content):
        full_path = self.resolve_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w") as f:
            f.write(content)

        return "File berhasil ditulis"

    def edit_file(self, path, old_string, new_string):
        full_path = self.resolve_path(path)

        with open(full_path) as f:
            content = f.read()

        if old_string not in content:
            return "String lama tidak ditemukan"

        content = content.replace(old_string, new_string, 1)

        with open(full_path, "w") as f:
            f.write(content)

        return "File berhasil diedit"
```

Versi ini sengaja dibuat sangat lurus supaya ide dasarnya kelihatan:

- resolve path
- baca/tulis/edit file

---

## Cara Menghubungkan Rewrite Sederhana Dengan Code Asli

Biar tidak bingung, mapping-nya begini:

### `commands.py`

- `SimpleCommandRunner` setara ide dasarnya dengan `CommandTools`
- bedanya `CommandTools` punya:
  - integrasi framework `Toolkit`
  - command policy
  - logging
  - output truncation
  - helper method terpisah

Jadi code asli itu bukan beda konsep.  
Dia cuma versi yang lebih production-ready.

---

### `file_system.py`

- `SimpleFileTools` setara ide dasarnya dengan `FileSystemTools`
- bedanya `FileSystemTools`:
  - terhubung ke `Toolkit`
  - method-nya didaftarkan sebagai tool agent

Sisanya secara logika hampir sama.

---

## Cara Baca File Seperti Ini Biar Nggak Pusing

Kalau ketemu file framework-ish begini, jangan baca dari atas sebagai "semua harus langsung ngerti".

Pecah jadi 4 pertanyaan:

1. class ini dibuat untuk apa?
2. method public yang didaftarkan ke framework apa saja?
3. helper method internal apa saja?
4. mana logika inti, mana boilerplate framework?

Kalau diterapkan ke sini:

### `commands.py`

- tujuan: tool eksekusi command
- public methods: `run_command`, `exec_command`
- helper: `_format_result`, `_handle_timeout`, `_handle_error`
- framework glue: `Toolkit`, `super().__init__(...)`

### `file_system.py`

- tujuan: tool akses file
- public methods: `read_file`, `write_file`, `edit_file`
- helper: `_resolve`
- framework glue: `Toolkit`, `super().__init__(...)`

Kalau dibaca dengan cara itu, file-nya jauh lebih masuk akal.

---

## Penilaian Jujur Soal Kodenya

Menurutku dua file ini justru cukup oke untuk ukuran tool wrapper:

- kecil
- fokus
- tanggung jawabnya jelas
- ada guardrail dasar

Yang bikin susah cuma:

- kamu harus kenal `Toolkit`
- kamu harus nyaman dengan OOP Python
- ada type hint modern

Kalau belum biasa, rasanya memang seperti "kok ini bukan Python yang biasa saya lihat ya?"

Itu normal banget.

---

## Kesimpulan Singkat

Kalau diringkas sependek mungkin:

- `commands.py` = pembungkus aman buat jalanin command terminal
- `file_system.py` = pembungkus aman buat operasi file di dalam folder tertentu
- syntax yang terasa asing itu mayoritas berasal dari:
  - Python modern
  - OOP
  - integrasi framework `Toolkit`

Jadi problem utamanya bukan kamu tidak bisa Python, tapi kamu lagi lihat **Python yang sudah masuk ke layer framework**.

Itu level abstraksinya memang satu langkah di atas script biasa.

---

## Kalau Mau Lanjut Belajar Dari Sini

Urutan paling enak menurutku:

1. pahami dulu versi rewrite sederhana di dokumen ini
2. balik lagi ke code asli
3. cocokkan bagian per bagian
4. baru lihat `Toolkit` dari `agno` sebagai "mesin yang memakai method-method ini"

Kalau kamu mau, next saya bisa bikinin lanjutan:

- `explain-toolkit-flow.md` untuk jelasin gimana `Toolkit` bekerja di balik layar
- atau `explain-tools-super-simple.md` yang isinya diagram alur super ringkas

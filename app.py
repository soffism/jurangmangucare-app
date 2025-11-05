# app.py (versi filter entitas berdasarkan JenisAnggota)
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO
from functools import wraps

app = Flask(__name__)
app.secret_key = "jurangmangucare_secret"

# ------------------------
# DATABASE CONNECTION
# ------------------------
def get_connection(entitas=None):
    if not entitas:
        entitas = 'jurangmangucare'

    if entitas == 'jurangmangucare':
        db_name = 'jurangmangucare.db'
    elif entitas == 'dkm':
        db_name = 'DKMAshShiddiq.db'
    else:
        raise ValueError("Entitas tidak dikenal: {}".format(entitas))

    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

# Decorator untuk memastikan pengguna sudah login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Ini adalah pengecekan autentikasi dasar
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------
# FUNGSI BANTUAN OTENTIKASI ANGGOTA (Perbaikan: Memastikan KodeAnggota terdaftar)
# ------------------------
def is_valid_anggota_user(kode_anggota, password):
    """
    Memeriksa apakah Kode Anggota terdaftar di salah satu entitas (DB) 
    dan password-nya adalah '2468'. Mengembalikan entitas jika ditemukan.
    """
    # 1. Cek Password (Hardcoded)
    if password != "2468":
        return None # Password salah

    # 2. Cek di kedua entitas/database
    for entitas_name in ['jurangmangucare', 'dkm']:
        conn = None
        try:
            conn = get_connection(entitas_name)
            cursor = conn.cursor()
            # Cek keberadaan KodeAnggota di tabel Anggota
            cursor.execute("SELECT KodeAnggota FROM Anggota WHERE KodeAnggota = ?", (kode_anggota,))
            if cursor.fetchone():
                return entitas_name # Anggota ditemukan di entitas ini
        except Exception as e:
            # Lewati jika ada masalah koneksi ke salah satu DB
            print(f"Error checking user in {entitas_name}: {e}")
            continue
        finally:
            if conn:
                conn.close()
    
    return None # Anggota tidak ditemukan di entitas manapun


# ------------------------
# ROUTE: Login
# ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # --- BLOK ADMIN (PERUBAHAN UTAMA) ---
        if username == "admin" and password == "13579":
            session["user"] = "admin"
            # SET BARU: Default admin ke entitas DKM Ash Shiddiq
            session["entitas"] = "dkm"  
            # REDIRECT BARU: Langsung ke laporan posisi keuangan
            return redirect(url_for("lap_posisi_keuangan"))
        # ------------------------------------

        elif password == "2468":
            session["user"] = username

            # Cek entitas berdasarkan JenisAnggota (Logika User Biasa TIDAK BERUBAH)
            conn = get_connection('jurangmangucare')
            jmcare_check = conn.execute("""
                SELECT 1 FROM Anggota 
                WHERE KodeAnggota = ? AND JenisAnggota LIKE '%JMCare%'
            """, (username,)).fetchone()
            conn.close()

            if jmcare_check:
                session["entitas"] = "jurangmangucare"
            else:
                session["entitas"] = "dkm"

            # Redirect user biasa ke index (yang akan mengarahkan ke halaman default mereka)
            return redirect(url_for("index"))

        else:
            return render_template("login.html", error="Username atau password salah.")
    
    return render_template("login.html")

# ------------------------
# ROUTE: Logout
# ------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------------
# ROUTE: Index (Root) - SUDAH FINAL
# ------------------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    # Admin atau User DKM akan masuk ke Laporan Posisi Keuangan
    if session["user"] == "admin" or session.get("entitas") == "dkm":
        return redirect(url_for("lap_posisi_keuangan")) 
    
    # User JMCare (user non-admin, entitas jurangmangucare)
    else:
        return redirect(url_for("transaksi_jmcare")) 

# ------------------------
# ROUTE: Tanbahan untuk Ganti Entitas)
# ------------------------
@app.route('/ganti_entitas_proses', methods=['POST'])
def ganti_entitas_proses():
    """Route untuk mengganti entitas aktif (DKM/JurangmanguCare) dan menyimpan di session."""
    
    # 1. Pastikan hanya admin yang bisa mengakses
    if session.get('user') != 'admin':
        flash('Akses ditolak.', 'error')
        return redirect(url_for('index'))

    # 2. Ambil entitas baru dari formulir
    entitas_baru = request.form.get('entitas')
    
    # 3. Validasi dan simpan ke session
    if entitas_baru in ['dkm', 'jurangmangucare']:
        session['entitas'] = entitas_baru
        flash(f'Entitas berhasil diganti menjadi {entitas_baru.upper()}.', 'success')
    else:
        flash('Pilihan entitas tidak valid.', 'error')
        
    # 4. Redirect kembali ke halaman tempat permintaan berasal
    # Menggunakan request.referrer agar tetap di halaman yang sama setelah ganti entitas
    return redirect(request.referrer or url_for('index'))

# ------------------------
# ROUTE: Rekap Akhir (Dinamis Berdasar Entitas)
# ------------------------
@app.route("/rekapakhir", methods=["GET", "POST"])
def rekapakhir():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    # Pilihan entitas disimpan ke session
    if request.method == "POST" and "entitas" in request.form:
        session["entitas"] = request.form["entitas"]

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    # Pilih view dan file template berdasarkan entitas
    if entitas == "dkm":
        rows = conn.execute("SELECT * FROM ViewLaporanRingkasan").fetchall()
    else:
        rows = conn.execute("SELECT * FROM RekapAkhir").fetchall()

    conn.close()
    return render_template("rekap_akhir.html", data=rows)


@app.route("/rekapakhir/export")
def export_rekapakhir():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    if entitas == "dkm":
        df = pd.read_sql_query("SELECT * FROM ViewLaporanRingkasan", conn)
        filename = "RekapAkhir_DKM.xlsx"
    else:
        df = pd.read_sql_query("SELECT * FROM RekapAkhir", conn)
        filename = "RekapAkhir_JMCare.xlsx"

    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RekapAkhir')
    output.seek(0)

    response = make_response(output.read())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

# ------------------------
# ROUTE: Rekap Akhir untuk DKM
# ------------------------
@app.route("/rekapakhir_dkm")
def rekapakhir_dkm():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    conn = get_connection("dkm")  # Ambil koneksi ke DB DKM
    rows = conn.execute("SELECT * FROM ViewLaporanRingkasan").fetchall()
    conn.close()
    return render_template("rekap_akhir_dkm.html", data=rows)

# ------------------------
# ROUTE: Export Rekap Akhir DKM ke Excel
# ------------------------
@app.route("/rekapakhir_dkm/export")
def export_rekapakhir_dkm():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    conn = get_connection("dkm")
    df = pd.read_sql_query("SELECT * FROM ViewLaporanRingkasan", conn)
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RekapAkhirDKM')
    output.seek(0)

    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=RekapAkhir_DKM.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

# ------------------------
# ROUTE: Rekap Transaksi (ViewRekapTransaksi)
# ------------------------
@app.route("/rekaptransaksi", methods=["GET", "POST"])
def index_viewrekap():
    if "user" not in session:
        return redirect(url_for("login"))

    # == BLOK INISIALISASI VARIABEL ==
    # Tangkap entitas dari dropdown jika dikirim lewat POST
    if request.method == "POST" and "entitas" in request.form:
        session["entitas"] = request.form["entitas"]

    entitas = session.get("entitas", "jurangmangucare")

    # Tentukan filter JenisAnggota sesuai entitas
    if entitas == "dkm":
        jenis_anggota_1 = "Anggota MAS" 
    else:
        jenis_anggota_1 = "Orang JMCare"
    
    jenis_anggota_2 = "AkunInternal"
    
    conn = get_connection(entitas)

    # 1. AMBIL DAFTAR ANGGOTA UNTUK DROPDOWN FILTER (UNTUK ADMIN)
    anggota_list = conn.execute("""
        SELECT KodeAnggota, NamaAnggota FROM Anggota
        WHERE JenisAnggota IN (?, ?) 
        ORDER BY NamaAnggota
    """, (jenis_anggota_1, jenis_anggota_2)).fetchall()

    # 2. LOGIKA UTAMA QUERY DATA REKAP (MENGGUNAKAN QUERY JOINS LENGKAP)
    base_query = """
        SELECT 
            T.No,
            H.Tanggal,
            T.KodeAnggota,
            A.NamaAnggota,
            T.KodeJenisTrans,
            J.JenisTransaksi,
            T.Uraian,
            T.Jumlah
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        JOIN Anggota A ON T.KodeAnggota = A.KodeAnggota
        JOIN JenisTransaksi J ON T.KodeJenisTrans = J.KodeJenisTrans
    """
    query_params = []
    
    # === POIN PERBAIKAN: INISIALISASI anggota_filter ===
    anggota_filter = None
    # ==================================================
    
    # 3. FILTER LOGIKA (Diterapkan di JOIN)
    
    # Filter pertama: Selalu batasi berdasarkan JenisAnggota entitas yang valid
    base_query += " WHERE A.JenisAnggota IN (?, ?)"
    query_params = [jenis_anggota_1, jenis_anggota_2]
    
    # Tambahkan pengurutan standar
    base_query += " ORDER BY H.Tanggal DESC, T.No DESC"

    # Penentuan Query Akhir (Filter Tambahan)
    if session["user"] == "admin":
        # ADMIN: Cek apakah ada filter Anggota dari form POST
        if request.method == "POST":
            anggota_filter = request.form.get("kode_anggota")
            if anggota_filter:
                # Tambahkan filter KodeAnggota
                base_query = base_query.replace(" ORDER BY", " AND T.KodeAnggota = ? ORDER BY")
                query_params.append(anggota_filter)
        
    else:
        # USER BIASA: Selalu filter berdasarkan user yang login
        anggota_filter = session["user"]
        base_query = base_query.replace(" ORDER BY", " AND T.KodeAnggota = ? ORDER BY")
        query_params.append(anggota_filter)

    # Eksekusi Query
    rows = conn.execute(base_query, tuple(query_params)).fetchall()

    conn.close()
    
    # Kirim daftar anggota untuk mengisi dropdown
    return render_template("rekap_transaksi_anggota.html", 
                           data=rows, 
                           kode=anggota_filter,
                           anggota_list=anggota_list)


# ------------------------
# ROUTE: Transaksi JMCARE (lihat semua transaksi)
# ------------------------
@app.route("/transaksi_jmcare")
def transaksi_jmcare():
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    kode_anggota = session["user"]

    conn = get_connection(entitas)
    rows = conn.execute("""
        SELECT Tanggal, KodeAnggota, NamaAnggota, KodeJenisTrans, JenisTransaksi, Jumlah, Uraian
        FROM ViewTransaksiLengkap
        WHERE KodeAnggota = ?
        ORDER BY Tanggal DESC
    """, (kode_anggota,)).fetchall()
    conn.close()

    return render_template("transaksi_user.html", data=rows, judul="Transaksi JurangmanguCare")


# ------------------------
# ROUTE: Transaksi Anggota (lihat semua transaksi)
# ------------------------
@app.route("/transaksi")
def transaksi_user():
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    kode_anggota = session["user"]

    conn = get_connection(entitas)

    rows = conn.execute("""
        SELECT 
            T.No,
            H.Tanggal,
            T.KodeAnggota,
            A.NamaAnggota,
            T.KodeJenisTrans,
            J.JenisTransaksi,
            T.Uraian,
            T.Jumlah
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        JOIN Anggota A ON T.KodeAnggota = A.KodeAnggota
        JOIN JenisTransaksi J ON T.KodeJenisTrans = J.KodeJenisTrans
        WHERE T.KodeAnggota = ?
        ORDER BY H.Tanggal DESC, T.No DESC
    """, (kode_anggota,)).fetchall()

    conn.close()
    return render_template("transaksi_user.html", data=rows)

# ------------------------
# ROUTE: Pivot Transaksi
# ------------------------
@app.route("/pivot")
def pivot_transaksi():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas") or "jurangmangucare"
    conn = get_connection(entitas)
    rows = conn.execute("SELECT * FROM ViewPivotTransaksi").fetchall()
    conn.close()
    return render_template("pivot_transaksi.html", data=rows)

# ------------------------
# ROUTE: Tambah Transaksi
# ------------------------
@app.route("/tambah", methods=["GET", "POST"])
def tambah():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    # Tangkap entitas yang dipilih di form
    if request.method == "POST" and "entitas" in request.form:
        session["entitas"] = request.form["entitas"]

    entitas = session.get("entitas", "jurangmangucare")
    
    # --- LOGIKA FILTER ANGGOTA YANG DIPERBAHARUI DAN SEDERHANA ---
    if entitas == "dkm":
        # DKM hanya menampilkan Anggota MAS dan AkunInternal
        # Jika Anda sudah mengganti 'Orang MAS' menjadi 'Anggota MAS', gunakan yang baru
        tipe_anggota_entitas = "Anggota MAS" 
    else: # jurangmangucare
        # JMCare hanya menampilkan Orang JMCare dan AkunInternal
        tipe_anggota_entitas = "Orang JMCare" 
    # -------------------------------------------------------------

    conn = get_connection(entitas)
    
    # Query hanya mengambil anggota tipe entitas terkait ATAU AkunInternal
    anggota_list = conn.execute("""
        SELECT KodeAnggota, NamaAnggota FROM Anggota
        WHERE JenisAnggota IN (?, 'AkunInternal')
        ORDER BY NamaAnggota
    """, (tipe_anggota_entitas,)).fetchall()

    jenis_list = conn.execute("""
        SELECT KodeJenisTrans, JenisTransaksi FROM JenisTransaksi
    """).fetchall()

    # ... (Sisa kode untuk all_trans_data dan POST logic tetap sama)
    # ... (Pastikan bagian return di akhir juga mengembalikan anggota_list)
    
    # Ambil semua data transaksi untuk tabel di bawah
    all_trans_data = conn.execute("""
        SELECT T.No, T.KodeAnggota, T.KodeJenisTrans, T.Uraian, T.Jumlah, H.Tanggal
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        ORDER BY T.No DESC 
    """).fetchall()
    
    last_entry = None
    if request.method == "POST":
        # Logika POST (diasumsikan sudah benar)
        if "tanggal" not in request.form:
            conn.close()
            return render_template("tambah_transaksi.html",
                                   anggota_list=anggota_list,
                                   jenis_list=jenis_list,
                                   last_trans=None,
                                   all_trans_data=all_trans_data,
                                   today=datetime.today().strftime("%Y-%m-%d"))

        # Proses transaksi seperti biasa
        tanggal_input = request.form.get("tanggal")
        kode_anggota = request.form.get("kode_anggota")
        kode_jenis = request.form.get("kode_jenis")
        uraian = request.form.get("uraian")
        jumlah = request.form.get("jumlah")

        try:
           datetime.strptime(tanggal_input, "%Y-%m-%d")
        except ValueError:
            flash("Format tanggal tidak valid.", "error")
            return redirect(url_for("tambah"))


        result = conn.execute("SELECT IDTanggal FROM HeaderTransaksi WHERE Tanggal = ?", (tanggal_input,)).fetchone()
        if result:
            kd_tanggal = result["IDTanggal"]
        else:
            conn.execute("INSERT INTO HeaderTransaksi (Tanggal) VALUES (?)", (tanggal_input,))
            kd_tanggal = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO Transaksi (KodeAnggota, KodeJenisTrans, Uraian, Jumlah, KdTanggal)
            VALUES (?, ?, ?, ?, ?)
        """, (kode_anggota, kode_jenis, uraian, jumlah, kd_tanggal))
        conn.commit()

        last_entry = conn.execute("""
            SELECT T.*, H.Tanggal FROM Transaksi T
            JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
            WHERE T.rowid = last_insert_rowid()
        """).fetchone()

    conn.close()
    return render_template("tambah_transaksi.html",
                           anggota_list=anggota_list,
                           jenis_list=jenis_list,
                           last_trans=last_entry,
                           all_trans_data=all_trans_data, # DIGANTI
                           today=datetime.today().strftime("%Y-%m-%d"))

# ------------------------
# ROUTE: Edit Transaksi
# ------------------------
# ------------------------
# ROUTE: Edit Transaksi
# ------------------------
@app.route("/edit_transaksi/<int:id>", methods=["GET", "POST"])
def edit_transaksi(id):
    # Pengecekan Autentikasi (Diasumsikan login_required sudah diterapkan atau admin saja)
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    
    # --- PERBAIKAN LOGIKA FILTER ANGGOTA ---
    if entitas == "dkm":
        # Gunakan tipe yang konsisten dengan route /tambah
        tipe_anggota_entitas = "Anggota MAS"
    else:
        # Gunakan tipe yang konsisten dengan route /tambah
        tipe_anggota_entitas = "Orang JMCare"
    # -------------------------------------

    conn = get_connection(entitas)

    if request.method == "POST":
        kode_anggota = request.form.get("kode_anggota")
        kode_jenis = request.form.get("kode_jenis")
        uraian = request.form.get("uraian")
        jumlah = request.form.get("jumlah")

        conn.execute("""
            UPDATE Transaksi
            SET KodeAnggota=?, KodeJenisTrans=?, Uraian=?, Jumlah=?
            WHERE No=?
        """, (kode_anggota, kode_jenis, uraian, jumlah, id))
        conn.commit()
        conn.close()
        # Setelah berhasil, redirect kembali ke halaman tambah/daftar transaksi
        flash("Transaksi berhasil diperbarui.", "success")
        return redirect(url_for("tambah"))

    # --- Ambil data transaksi yang akan di-edit
    data = conn.execute("""
        SELECT T.*, H.Tanggal AS TglTransaksi
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        WHERE T.No = ?
    """, (id,)).fetchone()

    if data is None:
        conn.close()
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("tambah"))

    # --- Ambil Daftar Anggota dengan filter yang sudah diperbaiki
    anggota_list = conn.execute("""
        SELECT KodeAnggota, NamaAnggota FROM Anggota
        WHERE JenisAnggota IN (?, 'AkunInternal')
        ORDER BY NamaAnggota
    """, (tipe_anggota_entitas,)).fetchall()

    # --- Ambil Daftar Jenis Transaksi
    jenis_list = conn.execute("""
        SELECT KodeJenisTrans, JenisTransaksi FROM JenisTransaksi
        ORDER BY KodeJenisTrans
    """).fetchall()

    conn.close()

    return render_template("edit_transaksi.html", data=data, anggota_list=anggota_list, jenis_list=jenis_list)

# ------------------------
# ROUTE: Hapus Transaksi
# ------------------------
@app.route("/hapus_transaksi/<int:id>", methods=["GET", "POST"])
def hapus_transaksi(id):
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas") or "jurangmangucare"
    conn = get_connection(entitas)

    transaksi = conn.execute("""
        SELECT T.No, T.KodeAnggota, T.KodeJenisTrans, T.Uraian, T.Jumlah, H.Tanggal
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        WHERE T.No = ?
    """, (id,)).fetchone()

    if request.method == "POST":
        # Pastikan Anda sudah punya tabel LogHapusTransaksi jika ingin logging
        try:
            conn.execute("""
                INSERT INTO LogHapusTransaksi (NoTransaksi, KodeAnggota, KodeJenisTrans, Uraian, Jumlah, Tanggal, DihapusOleh, WaktuPenghapusan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaksi["No"],
                transaksi["KodeAnggota"],
                transaksi["KodeJenisTrans"],
                transaksi["Uraian"],
                transaksi["Jumlah"],
                transaksi["Tanggal"],
                session.get("user"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        except:
            pass  # Abaikan kalau LogHapusTransaksi belum ada

        conn.execute("DELETE FROM Transaksi WHERE No = ?", (id,))
        conn.commit()
        conn.close()
        return redirect(url_for("tambah"))

    conn.close()
    return render_template("konfirmasi_hapus.html", transaksi=transaksi)

# ------------------------
# ROUTE: Tambah Anggota (CREATE & READ)
# ------------------------
@app.route("/tambah_anggota", methods=["GET", "POST"])
def tambah_anggota():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    # --- Filter Entitas ---
    if entitas == "dkm":
        tipe_anggota_entitas = "Anggota MAS" 
    else:
        tipe_anggota_entitas = "Orang JMCare" 

    if request.method == "POST":
        # PERUBAHAN: Ambil NoAnggota dari form (input manual)
        no_anggota_str = request.form["no_anggota"].strip()
        kode = request.form["kode_anggota"].strip().upper()
        nama = request.form["nama_anggota"].strip()
        jenis = request.form["jenis_anggota"].strip()

        # 1. Cek apakah KodeAnggota sudah ada
        exists_kode = conn.execute("SELECT 1 FROM Anggota WHERE KodeAnggota = ?", (kode,)).fetchone()
        
        if exists_kode:
            flash(f"Kode anggota '{kode}' sudah ada. Gunakan kode lain.", "error")
            conn.close()
            return redirect(url_for("tambah_anggota"))
            
        # 2. Cek apakah NoAnggota sudah ada
        # Menggunakan no_anggota_str karena kolom DB masih TEXT
        exists_no = conn.execute("SELECT 1 FROM Anggota WHERE NoAnggota = ?", (no_anggota_str,)).fetchone()
        
        if exists_no:
            flash(f"No. Anggota '{no_anggota_str}' sudah ada. Gunakan nomor lain.", "error")
            conn.close()
            return redirect(url_for("tambah_anggota"))

        else:
            try:
                # Lakukan INSERT menggunakan NoAnggota manual yang sudah diinput
                conn.execute("INSERT INTO Anggota (NoAnggota, KodeAnggota, NamaAnggota, JenisAnggota) VALUES (?, ?, ?, ?)",
                             (no_anggota_str, kode, nama, jenis))
                conn.commit()
                
                # Menggunakan no_anggota_str (string) untuk pesan sukses
                flash(f"Anggota '{nama}' ({kode}) berhasil ditambahkan dengan NoAnggota {no_anggota_str}.", "success")

            except Exception as e:
                conn.rollback()
                # Menggunakan str(e) untuk penanganan error yang aman.
                flash(f"Terjadi kesalahan saat menambahkan anggota: {str(e)}", "error")

            finally:
                conn.close()
                return redirect(url_for("tambah_anggota"))

    # --- LOGIKA SORTING (READ/GET) ---
    sort_by = request.args.get("sort", "no_desc") 
    
    order_map = {
        # DIKEMBALIKAN: Menggunakan CAST karena DB column masih TEXT
        "no_asc": "CAST(NoAnggota AS INTEGER) ASC",
        "no_desc": "CAST(NoAnggota AS INTEGER) DESC",
        "jenis_asc": "JenisAnggota ASC, CAST(NoAnggota AS INTEGER) ASC"
    }
    
    order_clause = order_map.get(sort_by, "CAST(NoAnggota AS INTEGER) DESC")

    # Ambil daftar seluruh anggota untuk GET request
    try:
        anggota_list = conn.execute(f"""
            SELECT * FROM Anggota 
            WHERE JenisAnggota IN (?, 'AkunInternal')
            ORDER BY {order_clause}
        """, (tipe_anggota_entitas,)).fetchall()
    except Exception as e:
        anggota_list = []
        flash(f"Terjadi kesalahan saat memuat daftar anggota: {str(e)}", "error")
    
    conn.close()
    
    return render_template("tambah_anggota.html", 
                           anggota_list=anggota_list, 
                           current_sort=sort_by)

# ------------------------
# ROUTE: Edit Anggota (Update)
# ------------------------
@app.route("/edit_anggota/<kode>", methods=["GET", "POST"])
def edit_anggota(kode):
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)
    anggota_data = conn.execute("SELECT * FROM Anggota WHERE KodeAnggota = ?", (kode,)).fetchone()

    if request.method == "POST":
        nama = request.form["nama_anggota"].strip()
        jenis = request.form["jenis_anggota"].strip()

        conn.execute("UPDATE Anggota SET NamaAnggota = ?, JenisAnggota = ? WHERE KodeAnggota = ?",
                     (nama, jenis, kode))
        conn.commit()
        conn.close()
        
        flash(f"Data anggota '{kode}' berhasil diperbarui.", "success")
        return redirect(url_for("tambah_anggota"))
    
    conn.close()
    
    if anggota_data is None:
        flash("Anggota tidak ditemukan.", "error")
        return redirect(url_for("tambah_anggota"))

    # Anda harus menyediakan template 'edit_anggota.html'
    return render_template("edit_anggota.html", data=dict(anggota_data))


# ------------------------
# ROUTE: Hapus Anggota (Delete)
# ------------------------
@app.route("/hapus_anggota/<kode>", methods=["GET", "POST"])
def hapus_anggota(kode):
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)
    anggota_data = conn.execute("SELECT * FROM Anggota WHERE KodeAnggota = ?", (kode,)).fetchone()
    
    if anggota_data is None:
        flash("Anggota tidak ditemukan.", "error")
        conn.close()
        return redirect(url_for("tambah_anggota"))

    if request.method == "POST":
        # Hapus data anggota
        conn.execute("DELETE FROM Anggota WHERE KodeAnggota = ?", (kode,))
        conn.commit()
        conn.close()
        
        flash(f"Anggota '{kode}' berhasil dihapus.", "success")
        return redirect(url_for("tambah_anggota"))
    
    conn.close()
        
# ------------------------
# ROUTE: Tambah Jenis Transaksi
# ------------------------
@app.route("/tambah_jenis", methods=["GET", "POST"])
def tambah_jenis():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    message = None

    if request.method == "POST":
        kode = request.form["kode"]
        nama = request.form["nama"]

        conn = get_connection(entitas)
        existing = conn.execute("SELECT 1 FROM JenisTransaksi WHERE KodeJenisTrans = ?", (kode,)).fetchone()

        if existing:
            message = f"Kode Jenis Transaksi '{kode}' sudah ada. Gunakan kode lain."
        else:
            conn.execute("INSERT INTO JenisTransaksi (KodeJenisTrans, JenisTransaksi) VALUES (?, ?)", (kode, nama))
            conn.commit()
            message = f"Jenis Transaksi '{nama}' berhasil ditambahkan."
        conn.close()

    return render_template("tambah_jenis.html", message=message)


# ------------------------
# ROUTE: Rekap Anggota
# ------------------------

@app.route("/rekapanggota", methods=["GET", "POST"])
def rekapanggota():
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    # Pilih view dan file template berdasarkan entitas
    if entitas == "dkm":
        rows = conn.execute("SELECT * FROM ViewLaporanRingkasan").fetchall()
        template_name = "rekap_anggota_dkm.html"
    else:
        rows = conn.execute("SELECT * FROM RekapAkhir").fetchall()
        template_name = "rekap_anggota_jmcare.html"

    conn.close()
    return render_template(template_name, data=rows)


# ------------------------
# ROUTES: Laporan Keuangan DKM Ash Shiddiq (Wajib Entitas DKM)
# ------------------------

def get_report_data(view_name, entitas="dkm"):
    """Fungsi helper untuk mengambil data laporan keuangan DKM."""
    if entitas != "dkm":
        flash("Laporan Keuangan hanya tersedia untuk DKM Ash Shiddiq.", "warning")
        return []
        
    conn = get_connection(entitas)
    try:
        query = f"SELECT * FROM {view_name}"
        rows = conn.execute(query).fetchall()
        
        # PERBAIKAN KRITIS: Konversi sqlite3.Row ke dict standar Python
        # Ini akan memastikan Jinja2 mengakses kolom dengan nama yang sama persis
        data_dicts = [dict(row) for row in rows]
        return data_dicts
        
    except sqlite3.OperationalError as e:
        flash(f"Error Database: View '{view_name}' tidak ditemukan. Pesan: {e}", "error")
        return []
    finally:
        conn.close()


# ------------------------
# ROUTES: Helper 2 (Wajib Entitas DKM)
# ------------------------
def get_master_data(table_name, entitas):
    """Fungsi helper untuk mengambil semua data dari tabel master (Anggota atau JenisTransaksi)."""
    conn = get_connection(entitas)
    try:
        query = f"SELECT * FROM {table_name}"
        rows = conn.execute(query).fetchall()
        
        # Konversi sqlite3.Row ke dict
        data_dicts = [dict(row) for row in rows]
        return data_dicts
        
    except sqlite3.OperationalError as e:
        # Menangani jika tabel master tidak ditemukan (meski jarang)
        print(f"Error Database: Tabel '{table_name}' tidak ditemukan. Pesan: {e}")
        return []
    finally:
        conn.close()

def get_anggota_dict(entitas):
    """Mengambil data anggota dan mengonversinya menjadi dictionary untuk lookup cepat."""
    anggota_list = get_master_data("Anggota", entitas)
    # Membuat dictionary: { 'KodeAnggota': 'NamaAnggota' }
    return {a['KodeAnggota']: a['NamaAnggota'] for a in anggota_list}

def get_jenis_dict(entitas):
    """Mengambil data jenis transaksi dan mengonversinya menjadi dictionary untuk lookup cepat."""
    jenis_list = get_master_data("JenisTransaksi", entitas)
    # Membuat dictionary: { 'KodeJenisTrans': 'JenisTransaksi' }
    return {j['KodeJenisTrans']: j['JenisTransaksi'] for j in jenis_list}


# ... (route lap_posisi_keuangan dan route lainnya tidak berubah) ...

# ------------------------
# ROUTE: Laporan Posisi Keuangan (PERUBAHAN AKSES)
# ------------------------
@app.route("/lap_posisi_keuangan")
def lap_posisi_keuangan():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Izinkan jika Admin ATAU Entitas saat ini adalah DKM
    entitas = session.get("entitas", "jurangmangucare")
    is_admin = session.get("user") == "admin"
    
    if not is_admin and entitas != "dkm":
        flash("Laporan ini hanya tersedia untuk Administrator atau Anggota DKM Ash Shiddiq.", "error")
        return redirect(url_for("index"))

    # Nama VIEW tetap vw_LapPosisiKeuangan_Dinamis2
    data = get_report_data("vw_LapPosisiKeuangan_Dinamis2", entitas)

    return render_template("laporan_posisi_keuangan.html", data=data) 

# ------------------------
# ROUTE: Laporan Aktivitas (PERUBAHAN AKSES & LOGIKA)
# ------------------------
@app.route("/lap_aktivitas")
@login_required # <--- Decorator akan memeriksa sesi sebelum fungsi dijalankan
def lap_aktivitas():
    
    entitas = session.get("entitas")
    # Asumsi: view vw_LapAktivitas2 berisi kolom 'Rincian' (yang berupa Kode Anggota/JenisTransaksi dengan sufiks)
    data = get_report_data("vw_LapAktivitas2", entitas)
    
    # 1. Ambil data master untuk lookup cepat
    # Asumsi get_anggota_dict dan get_jenis_dict sudah didefinisikan (seperti di app_master_helpers.py)
    anggota_lookup = get_anggota_dict(entitas)
    jenis_lookup = get_jenis_dict(entitas)
    
    # 2. Sisipkan NamaAnggota dan JenisTransaksi ke setiap baris data
    for row in data:
        # Kolom yang memuat kode ringkas di laporan Anda adalah 'Rincian'
        kode_laporan = row.get('Rincian', '') 
        
        kode_anggota_asli = ''
        kode_jenis_asli = ''
        
        # Logika Pemrosesan Kode:
        # Cek apakah kode_laporan adalah kode Anggota atau Jenis Transaksi
        
        # (A) Coba Asosiasi sebagai Kode Anggota
        # Hapus sufiks setelah underscore (misal: INF_ADH_Dana -> INF_ADH)
        if '_' in kode_laporan:
            # Contoh: INF_ADH_Dana
            # Ambil bagian pertama (INF_ADH) sebagai potensi Kode Anggota
            potensi_anggota_kode = kode_laporan.split('_')[0] + '_' + kode_laporan.split('_')[1]
            # Cek apakah kode_laporan sama dengan kode OPE_ADH
            if kode_laporan.startswith('OPE_'):
              potensi_anggota_kode = kode_laporan
        
        # Kasus 1: Kode Laporan = OPE_ADH (Kode master sama dengan kode laporan)
        if kode_laporan in anggota_lookup:
            kode_anggota_asli = kode_laporan
        # Kasus 2: Kode Laporan = INF_ADH_Dana (Kode master INF_ADH)
        elif '_' in kode_laporan and potensi_anggota_kode in anggota_lookup:
            kode_anggota_asli = potensi_anggota_kode
        # Kasus 3: Kode Laporan memiliki sufiks, tapi hanya 1 pemisah (Misal: INF_RUT_Dana)
        elif kode_laporan.count('_') >= 2:
            kode_anggota_asli = kode_laporan.rsplit('_', 1)[0]
            
        # Jika berhasil menemukan Kode Anggota/Jenis Transaksi, lakukan lookup
        if kode_anggota_asli:
            row['KodeAnggotaLaporan'] = kode_anggota_asli
            row['NamaAnggota'] = anggota_lookup.get(kode_anggota_asli, 'Anggota Tidak Dikenal')
            row['KodeJenisTransLaporan'] = kode_anggota_asli
            row['JenisTransaksi'] = jenis_lookup.get(kode_anggota_asli, 'Jenis Transaksi Tidak Dikenal')
        else:
            # Jika tidak ada Kode Anggota yang cocok (mungkin ini adalah baris subtotal/judul)
            row['KodeAnggotaLaporan'] = ''
            row['NamaAnggota'] = 'T/A'
            row['KodeJenisTransLaporan'] = ''
            row['JenisTransaksi'] = 'T/A'
        
    # Render template dengan data yang sudah diperkaya
    return render_template("laporan_aktivitas.html", data=data)


@app.route("/saldo_akun")
def saldo_akun():
    # Periksa otentikasi admin
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas")
    
    # Ambil data dari VIEW saldo akun
    data = get_report_data("vw_SaldoAkun_Final2", entitas)
    
    # Render template
    return render_template("saldo_akun.html", data=data)


@app.route("/buku_besar")
def buku_besar():
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    data = get_report_data("vw_BukuBesar_Final2", session.get("entitas"))
    return render_template("buku_besar.html", data=data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


# Run in centos
```
docker ps
docker stop $(docker ps -a -q)
```
```
sudo yum install -y libjpeg-devel zlib-devel
sudo pip3 install reportlab
sudo pip3 install pillow
sudo pip3 install weasyprint
sudo pip3 install fitz
```

```
python manage.py runserver 0.0.0.0:8000
```

# update python 3.8 and 依赖
```
sudo yum install -y gcc make zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel \
openssl-devel libffi-devel wget xz xz-devel
```
```
cd /usr/src
sudo wget https://www.python.org/ftp/python/3.8.18/Python-3.8.18.tgz
sudo tar xzf Python-3.8.18.tgz
cd Python-3.8.18
sudo ./configure --enable-optimizations
sudo make altinstall
```
test python3.8
```
python3.8 -c "import _ctypes; print('✅ _ctypes OK')"
```
python3.8 -m pip install --upgrade pip
python3.8 -m pip install django weasyprint psycopg2-binary reportlab pymupdf
```
install postgresql
```
python3.8 -m pip install --upgrade pip setuptools wheel
python3.8 -m pip install psycopg2
```
```
python3.8 -m pip install openpyxl
python3.8 -m pip install pandas
```
```
python3.8 manage.py runserver 0.0.0.0:8000
```
# install postgresql
```
which psql
sudo yum install -y postgresql-server postgresql-contrib
sudo postgresql-setup initdb

sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo systemctl status postgresql
```
```
ss -ltnp | grep 5432

```

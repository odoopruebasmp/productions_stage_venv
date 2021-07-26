FROM python:2-slim-stretch

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN apt update -y --no-install-recommends && \
    apt install -y --no-install-recommends build-essential \
    libxslt-dev \
    libzip-dev \
    libldap2-dev \
    libsasl2-dev \ 
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev

RUN apt install -y python-cups && \
    apt install -y libcups2-dev gcc \
    && apt install -y cups

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install html2text \
    && pip install paramiko \
    && pip install xlsxwriter \
    && pip install xlrd \
    && pip install pandas \
    && pip install num2words \
    && pip install pycups==1.9.73 \
    && pip install progressbar2

RUN apt-get update && apt-get install -y git

RUN apt install -y gpg \
    && echo "deb http://deb.nodesource.com/node_8.x stretch main" > /etc/apt/sources.list.d/nodesource.list \
    && export GNUPGHOME="$(mktemp -d)" \
    && repokey='9FD3B784BC1C6FC31A8A0A1C1655A0AB68576280' \
    && gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "${repokey}" \
    && gpg --armor --export "${repokey}" | apt-key add - \
    && gpgconf --kill all \
    && rm -rf "$GNUPGHOME" \
    && apt-get update \
    && apt-get install -y nodejs \
    && npm install -g rtlcss \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g less less-plugin-clean-css

RUN git clone https://github.com/aeroo/aeroolib.git &&\
    cd aeroolib &&\
    git checkout py2.x && python setup.py install  

# RUN export PYTHONPATH=/usr/src/app/odoo:/usr/src/app/avancys:/usr/src/app/aeroo_report
RUN apt update -y
RUN apt install -y wget
RUN wget https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.4/wkhtmltox-0.12.4_linux-generic-amd64.tar.xz \
    && tar xvf wkhtmltox-0.12.4_linux-generic-amd64.tar.xz \
    && mv wkhtmltox/bin/wkhtmlto* /usr/bin/ \
    && ln -nfs /usr/bin/wkhtmltopdf /usr/local/bin/wkhtmltopdf


RUN groupadd -r odoo && useradd -r -g odoo odoo
RUN chown -R odoo:odoo /var/lib

RUN mkdir -p /var/lib/odoo \
    && chown -R odoo /var/lib/odoo

RUN mkdir -p /var/log/odoo \
    && chmod -R 777 /var/log/odoo

RUN mkdir -p /var/log/avancys \
    && chmod -R 777 /var/log/avancys

RUN mkdir -p /opt/openerp \
    && chmod -R 777 /opt/openerp

RUN mkdir -p /home/public \
    && chmod -R 777 /home/public \
    && chmod -R 777 /home/public

RUN mkdir -p /home/public \
    && chown -R odoo:odoo /home/public \
    && chmod -R 777 /home/public

# COPY ./aeroo_report/ /opt/openerp/aeroo_report
COPY ./avancys/ /opt/avancys
COPY api_avancys /opt/

RUN chmod -R 777 /opt/*
# COPY ./odoo/ /opt/openerp/odoo

COPY odoo-server.conf /etc/

USER odoo
CMD ["sh","-c","python /opt/openerp/odoo_v8/odoo.py -c '/etc/odoo-server.conf'"]

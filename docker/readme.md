Build:

within a directory, clone the repository into a folder named 'avancys' (gitlab access is required)
$ git clone https://gitlab.com/avancyserp/moreproducts.git avancys

add Dockerfile, odoo-server.conf, requirements.txt, api_avancys within the same directory,
structure should be:

avancys/
Dockerfile
odoo-server.conf
requirements.txt
api_avancy

Now you can build and push (dockerhub credentials required):

$ docker login
$ docker build -t avancys/odoo:odoo_v8_moreproducts .
$ docker push avancys/odoo:odoo_v8_moreproducts

Run:

container is run on server by:

$ docker login
$ docker pull avancys/odoo:odoo_v8_moreproducts
$ docker run --name odoo_docker_more --net=host -v /opt/openerp:/opt/openerp -v /home/public:/home/public -v /home/odoo/.local/share/Odoo:/var/lib/odoo -v /var/log/odoo:/var/log/odoo --restart always -d avancys/odoo:odoo_v8_moreproducts

These folders are required on the server to run the container:

/opt/openerp (contains odoo_v8 and aeroo_report_v8)
/home/public (sftp related folders)
/home/odoo/.local/share/Odoo (filestore)
/var/log/odoo (log folder)

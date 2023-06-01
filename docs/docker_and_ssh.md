If you cannot ssh via vpn to your machine after starting the docker service, this is likely due to overlapping addresses of docker networks and other stuff. 

follow these steps:

1. Stop all running containers
2. Remove existing docker networks by running `docker network prune`
3. Inspect if all networks were removed by running `docker network list`. Only networks with names `bridge` `host` and `none` should remain. If there are other networks, run `docker network rm [NETWORK ID]`. 
4. Edit/create the file `/etc/docker/daemon.json` and insert:
    ```
    {
    "default-address-pools" : [
            {
            "base" : "172.240.0.0/16",
            "size" : 24
            }
        ]
    } 
    ```
    This will tell docker to use the ip range `172.240.0.0/16` for newly created docker networks
5. Restart the machine 
6. Start the docker service: `systemctl start docker`
7. First time using docker compose, you should use `docker compose up --force-recreate`. This will recreate the deleted docker network, this time using an address from the `default-address-pools`. 
8. You should now be able to ssh


Adapted from https://www.lullabot.com/articles/fixing-docker-and-vpn-ip-address-conflicts 
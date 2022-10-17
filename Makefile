all:
	@echo nothing special

lint:
	yapf -ir .


DOCKER_RELEASE_TAG := pyslam_env
docker_build:
	docker build --tag ${DOCKER_RELEASE_TAG} .

enter_docker_env:
	docker run --rm \
		--gpus all \
		--network host \
		-v `pwd`:/pyslam \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
        -v ~/.Xauthority:/root/.Xauthority \
        -v ~/data:/data \
        -e DISPLAY=${DISPLAY} \
        -e GDK_SCALE \
        -e GDK_DPI_SCALE \
		-w /pyslam \
		-it ${DOCKER_RELEASE_TAG} bash
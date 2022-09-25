all:
	@echo nothing special

lint:
	yapf -ir .


DOCKER_RELEASE_TAG := pyslam_env
docker_build:
	docker build --tag ${DOCKER_RELEASE_TAG} .

enter_docker_env:
	docker run --rm \
		--network host \
		-v `pwd`:/pyslam \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
        -v ~/.Xauthority:/root/.Xauthority \
        -e DISPLAY=${DISPLAY} \
        -e GDK_SCALE \
        -e GDK_DPI_SCALE \
		-w /pyslam \
		-it ${DOCKER_RELEASE_TAG} bash
# MicroWrap

MicroWrap is a base container image designed to streamline and simplify the process of developing and deploying microservices through the use of containerization. Using it is as simple as writing a Dockerfile for your application, and including a `microwrap.json` configuration; see the example below:

```Dockerfile
# Create an image using microwrap as the base to serve as our runtime image
FROM michionlion/microwrap:latest
# Configure microwrap
COPY microwrap.json /microwrap.json
# Upload executable to expose as a service
COPY version.sh /version.sh
```

MicroWrap functions as an executable wrapper, abstracting the complexities of network communication and service execution away from the application itself. It consists of an HTTP server that listens for incoming HTTP requests and translates those HTTP requests to command-line invocations of the wrapped executable. The translation process supports parameters -- URL parameters embedded in the request will become `--option value` strings passed to the wrapped executable. The standard output of the wrapped executable will be returned as the body of the response to the triggering request.

As an example, suppose the following request was made to a container running microwrap:

```shell
http GET http://$HOST:$PORT/start?option1=test2&flag1
```

This request would trigger microwrap to execute its configured executable with:

```shell
/executable/path --option1 "test2" --flag1`
```

The standard output of the execution would be returned as the body of the response to the `GET` HTTP request, and if the executable exits with a non-zero return code, an HTTP 500 Internal Server Error is returned (with the body being the concatenated standard output and standard error streams).

## Usage

To make your application a containerized service, you will need to write a Dockerfile that builds an image. This image can then be used in many different containerized environments, such as Docker, OpenShift, Kubernetes, and others. The Dockerfile for your application needs to accomplish two tasks: allow execution of your program, and configure MicroWrap. To allow your program to execute, the Dockerfile should install dependencies that your program needs, compile your program, and configure the runtime environment so that your program can execute. Additionally, you may want to prepare mount points for any folders that may need to be accessed by your program for external reading/writing, in the case that such input/output is needed. An example (which specifically uses a Java program, but is applicable to many different languages and technologies) is given in the `example/` directory of this repository.

## Configuration

1. **Executable Path** This is the location of the executable file that will be executed per request. It should be an executable file in your image.
2. **Max Active Requests** This is the number of wrapped-executable invocations to allow at one time; any requests beyond this number will be queued for future invocation. Specify `-1` for no limit.
3. **Allowed Parameters** This is a list of URL parameters that will be passed through as command-line options to the wrapped executable. Any other parameters will be ignored.
4. **Default Parameters** This is an object which is mapped to `--attribute value` strings passed to the wrapped executable that can be overridden by URL parameters. Values that are `true` and `false` will not map to `"true"` or `"false"`, but instead value-less `--flag` and `--no-flag` (for an attribute named `flag`) strings; values that are `null` or the empty string `""` will cause the parameter to be ignored.

These configuration parameters should be specified in the `/microwrap.json` configuration file in your image:

```json
{
    "executablePath": "/root/program.sh",
    "maxActiveRequests": 1,
    "allowedParameters": ["option1", "flag1"],
    "defaultParameters": {
        "option1": "defaultValue1",
        "flag1": false,
        "flag2": true
    }
}
```

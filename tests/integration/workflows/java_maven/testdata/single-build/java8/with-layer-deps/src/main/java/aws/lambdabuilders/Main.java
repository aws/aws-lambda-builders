package aws.lambdabuilders;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;
import com.amazonaws.services.lambda.runtime.RequestHandler;

import aws.lambdabuilders.CommonCode;

public class Main implements RequestHandler<Object, Object> {
    public Object handleRequest(final Object input, final Context context) {
        final LambdaLogger logger = context.getLogger();
        CommonCode.doSomethingOnLayer(logger, "fromLambdaFunction");
        System.out.println("Hello AWS Lambda Builders!");
        return "Done";
    }
}

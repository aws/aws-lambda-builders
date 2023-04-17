package aws.lambdabuilders;

import com.amazonaws.services.lambda.runtime.LambdaLogger;

public class CommonCode {

    public static void doSomethingOnLayer(final LambdaLogger logger, final String s) {
        logger.log("Doing something on layer" + s);
    }
}

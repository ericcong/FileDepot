package boot;

import javax.annotation.*;

import org.slf4j.*;

import org.springframework.beans.factory.annotation.*;
import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.*;
import org.springframework.boot.builder.*;
import org.springframework.boot.context.web.*;
import org.springframework.context.annotation.*;

import org.springframework.web.servlet.config.annotation.*;

@Configuration
@EnableAutoConfiguration
@EnableWebMvc
@ComponentScan
public class Application extends SpringBootServletInitializer {

	private static final Logger log = LoggerFactory.getLogger(Application.class);
	
    @Override
    protected SpringApplicationBuilder configure(
    SpringApplicationBuilder springApplicationBuilder) {
		return springApplicationBuilder
			.sources(Application.class);
    }

    public static void main(String[] args) {
		new SpringApplicationBuilder(Application.class)
			.sources(Application.class)
			.build()
			.run(args);
    }    
}